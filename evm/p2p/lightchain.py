import asyncio
import logging
import traceback

from async_lru import alru_cache

from eth_keys import keys
from eth_utils import (
    decode_hex,
    encode_hex,
)

from evm.chains import Chain
from evm.exceptions import (
    BlockNotFound,
)
from evm.p2p.constants import HANDSHAKE_TIMEOUT
from evm.p2p import ecies
from evm.p2p.exceptions import (
    PeerDisconnected,
    UnreachablePeer,
    UselessPeer,
)
from evm.p2p.peer import (
    handshake,
    LESPeer,
)
from evm.p2p.utils import gen_request_id


class PeerPool:
    logger = logging.getLogger("evm.p2p.lightchain.PeerPool")
    # FIXME: Choose a better name
    _sleep = 10
    # FIXME: Must be passed in by callers
    privkey = ecies.generate_privkey()

    def __init__(self, chaindb, network_id, min_peers=3):
        self.chaindb = chaindb
        self.network_id = network_id
        self.min_peers = min_peers
        self.connected_nodes = {}
        self._should_stop = asyncio.Event()

    async def get_nodes_to_connect(self):
        from evm.p2p import kademlia
        from evm.chains.ropsten import RopstenChain
        from evm.chains.mainnet import MainnetChain
        if self.network_id == MainnetChain.network_id:
            return [
                kademlia.Node(
                    keys.PublicKey(decode_hex("1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082")),  # noqa: E501
                    kademlia.Address("52.74.57.123", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d")),  # noqa: E501
                    kademlia.Address("191.235.84.50", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("ddd81193df80128880232fc1deb45f72746019839589eeb642d3d44efbb8b2dda2c1a46a348349964a6066f8afb016eb2a8c0f3c66f32fadf4370a236a4b5286")),  # noqa: E501
                    kademlia.Address("52.231.202.145", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("3f1d12044546b76342d59d4a05532c14b85aa669704bfe1f864fe079415aa2c02d743e03218e57a33fb94523adb54032871a6c51b2cc5514cb7c7e35b3ed0a99")),  # noqa: E501
                    kademlia.Address("13.93.211.84", 30303, 30303)),
            ]
        elif self.network_id == RopstenChain.network_id:
            return [
                # Ropsten LES/1 nodes.
                kademlia.Node(
                    keys.PublicKey(decode_hex("88c2b24429a6f7683fbfd06874ae3f1e7c8b4a5ffb846e77c705ba02e2543789d66fc032b6606a8d8888eb6239a2abe5897ce83f78dcdcfcb027d6ea69aa6fe9")),  # noqa: E501
                    kademlia.Address("163.172.157.61", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("a1ef9ba5550d5fac27f7cbd4e8d20a643ad75596f307c91cd6e7f85b548b8a6bf215cca436d6ee436d6135f9fe51398f8dd4c0bd6c6a0c332ccb41880f33ec12")),  # noqa: E501
                    kademlia.Address("51.15.218.125", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("e80276aabb7682a4a659f4341c1199de79d91a2e500a6ee9bed16ed4ce927ba8d32ba5dea357739ffdf2c5bcc848d3064bb6f149f0b4249c1f7e53f8bf02bfc8")),  # noqa: E501
                    kademlia.Address("51.15.39.57", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("584c0db89b00719e9e7b1b5c32a4a8942f379f4d5d66bb69f9c7fa97fa42f64974e7b057b35eb5a63fd7973af063f9a1d32d8c60dbb4854c64cb8ab385470258")),  # noqa: E501
                    kademlia.Address("51.15.35.2", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("d40871fc3e11b2649700978e06acd68a24af54e603d4333faecb70926ca7df93baa0b7bf4e927fcad9a7c1c07f9b325b22f6d1730e728314d0e4e6523e5cebc2")),  # noqa: E501
                    kademlia.Address("51.15.132.235", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("482484b9198530ee2e00db89791823244ca41dcd372242e2e1297dd06f6d8dd357603960c5ad9cc8dc15fcdf0e4edd06b7ad7db590e67a0b54f798c26581ebd7")),  # noqa: E501
                    kademlia.Address("51.15.75.138", 30303, 30303)),
            ]
        else:
            raise ValueError("Unknown network_id: {}".format(self.network_id))

    async def run(self):
        while True:
            if self._should_stop.is_set():
                break
            try:
                await self.maybe_connect_to_more_peers()
            except:
                self.logger.error(
                    "Unexpected error ({}), restarting".format(traceback.format_exc()))
                # XXX: Not sure this is the best way to deal with unexpected errors, but this way
                # we can call run() with ensure_future() and know it will never stop.
                await self.stop_all_peers()

    async def maybe_connect_to_more_peers(self):
        for remote, peer in self.connected_nodes.items():
            if peer.is_finished():
                self.connected_nodes.pop(remote)

        if len(self.connected_nodes) >= self.min_peers:
            self.logger.debug(
                "Already connected to {} peers: {}; sleeping".format(
                    len(self.connected_nodes),
                    [remote for remote in self.connected_nodes]))
            await asyncio.sleep(self._sleep)
            return

        for node in self.get_nodes_to_connect():
            self.logger.debug("Connecting to {}".format(node))
            peer = await self.connect(node)
            if peer is not None:
                self.logger.info("Successfully connected to {}".format(peer))
                asyncio.ensure_future(peer.start())
                self.connected_nodes[peer.remote] = peer
        # XXX: Reconsider this sleep?
        await asyncio.sleep(self._sleep)

    async def stop_all_peers(self):
        await asyncio.gather(
            *[peer.stop_and_wait_until_finished() for peer in self.connected_nodes.values()])

    async def stop(self):
        self._should_stop.set()
        await self.stop_all_peers()

    async def connect(self, remote):
        if remote in self.connected_nodes:
            self.logger.debug("Skipping {}; already connected to it".format(remote))
            return None
        try:
            peer = await asyncio.wait_for(
                handshake(remote, self.privkey, LESPeer, self.chaindb, self.network_id),
                HANDSHAKE_TIMEOUT)
            return peer
        except (UnreachablePeer, asyncio.TimeoutError) as e:
            self.logger.debug("Failed to connect to {}: {}".format(remote, e))
        except UselessPeer:
            self.logger.debug("No matching capabilities with {}".format(remote))
        except PeerDisconnected as e:
            self.logger.debug(
                "{} disconnected before completing handshake; reason: {}".format(remote, e))
        except Exception as e:
            self.logger.warn("Unexpected error during auth/p2p handhsake with {}: {}".format(
                remote, e))
        return None


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
