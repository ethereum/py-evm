import logging

from async_lru import alru_cache

from eth_utils import encode_hex

from evm.chains import Chain
from evm.exceptions import (
    BlockNotFound,
)
from evm.p2p.utils import gen_request_id


class OnDemandDataBackend:
    logger = logging.getLogger("evm.p2p.lightchain.OnDemandDataBackend")
    # TODO:
    # 1. Use the PeerManager to maintain a set of connected peers
    # 2. Implement a queue of requests and a distributor which picks items from that queue and
    # sends them to one of our peers, ensuring the selected peer has the info we want and
    # respecting the flow control rules

    @alru_cache(maxsize=1024)
    async def get_block_by_hash(self, block_hash):
        peer = await self.get_peer()
        self.logger.debug("Fetching block {} from peer {}".format(encode_hex(block_hash), peer))
        request_id = gen_request_id()
        peer.les_proto.send_get_block_bodies([block_hash], request_id)
        reply = await peer.wait_for_reply(request_id)
        if len(reply['bodies']) == 0:
            raise BlockNotFound("No block with hash {} found".format(block_hash))
        return reply['bodies'][0]

    async def get_peer(self):
        raise NotImplementedError("TODO")

    async def stop(self):
        raise NotImplementedError("TODO")


class LightChain(Chain):
    on_demand_data_backend_class = None

    def __init__(self, chaindb, header=None):
        super(LightChain, self).__init__(chaindb, header=header)
        self.on_demand_data_backend = self.on_demand_data_backend_class(self.chaindb)

    async def stop(self):
        await self.on_demand_data_backend.stop()

    async def get_canonical_block_by_number(self, block_number):
        try:
            block_hash = self.chaindb.lookup_block_hash(block_number)
        except KeyError:
            raise BlockNotFound("No block with number {} found on canonical chain".format(
                block_number))
        return await self.get_block_by_hash(block_hash)

    async def get_block_by_hash(self, block_hash):
        # This will raise a BlockNotFound if we don't have the header in our DB, which is correct
        # because it means our peer doesn't know about it.
        header = self.chaindb.get_block_header_by_hash(block_hash)
        body = await self.on_demand_data_backend.get_block_by_hash(block_hash)
        block_class = self.get_vm_class_for_block_number(header.block_number).get_block_class()
        return block_class(
            header=header,
            transactions=body.transactions,
            uncles=body.uncles,
            chaindb=self.chaindb,
        )
