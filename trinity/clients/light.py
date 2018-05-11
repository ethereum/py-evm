import asyncio
import logging
from typing import List

from async_lru import alru_cache

from eth_utils import encode_hex

from eth_typing import (
    BlockNumber,
    Hash32,
    Address,
)

from evm.exceptions import HeaderNotFound
from evm.rlp.accounts import Account
from evm.rlp.blocks import BaseBlock
from evm.rlp.receipts import Receipt

from p2p.cancel_token import CancelToken
from p2p.peer import PeerPool
from p2p.service import BaseService

from trinity.chains.header import (
    BaseAsyncHeaderChain,
)
from trinity.db.header import (
    BaseAsyncHeaderDB,
)
from trinity.sync.light import (
    LightChainSyncer,
)


# How old (in seconds) must our local head be to cause us to start with a fast-sync before we
# switch to regular-sync.
FAST_SYNC_CUTOFF = 60 * 60 * 24


class LightClientNode(BaseService):
    logger: logging.Logger = logging.getLogger("trinity.clients.light.LightClientNode")

    header_chain: BaseAsyncHeaderChain = None
    headerdb: BaseAsyncHeaderDB = None

    def __init__(self,
                 header_chain: BaseAsyncHeaderChain,
                 headerdb: BaseAsyncHeaderDB,
                 peer_pool: PeerPool) -> None:
        super().__init__(CancelToken('FullNodeSyncer'))
        self.header_chain = header_chain
        self.headerdb = headerdb
        self.peer_pool = peer_pool
        self.syncer = LightChainSyncer(self.headerdb, self.peer_pool, self.cancel_token)

    async def _run(self) -> None:
        asyncio.ensure_future(self.peer_pool.run())
        await self.syncer.run()

    async def _cleanup(self):
        await self.peer_pool.cancel()

    #
    # API for fetching chain data over network.
    #
    async def get_canonical_block_by_number(self, block_number: BlockNumber) -> BaseBlock:
        """Return the block with the given number from the canonical chain.

        Raises HeaderNotFound if it is not found.
        """
        try:
            block_hash = await self.header_chain.coro_get_canonical_block_hash(block_number)
        except KeyError:
            raise HeaderNotFound(
                "No block with number {} found on local chain".format(block_number))
        return await self.get_block_by_hash(block_hash)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_block_by_hash(self, block_hash: Hash32) -> BaseBlock:
        peer = await self.get_best_peer()
        try:
            header = await self.headerdb.coro_get_block_header_by_hash(block_hash)
        except HeaderNotFound:
            self.logger.debug("Fetching header %s from %s", encode_hex(block_hash), peer)
            header = await peer.get_block_header_by_hash(block_hash, self.cancel_token)

        self.logger.debug("Fetching block %s from %s", encode_hex(block_hash), peer)
        body = await peer.get_block_by_hash(block_hash, self.cancel_token)
        block_class = self.get_vm_class_for_block_number(header.block_number).get_block_class()
        transactions = [
            block_class.transaction_class.from_base_transaction(tx)
            for tx in body.transactions
        ]
        return block_class(
            header=header,
            transactions=transactions,
            uncles=body.uncles,
        )

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_receipts(self, block_hash: Hash32) -> List[Receipt]:
        peer = await self.get_best_peer()
        self.logger.debug("Fetching %s receipts from %s", encode_hex(block_hash), peer)
        return await peer.get_receipts(block_hash, self.cancel_token)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_account(self, block_hash: Hash32, address: Address) -> Account:
        peer = await self.get_best_peer()
        return await peer.get_account(block_hash, address, self.cancel_token)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_contract_code(self, block_hash: Hash32, key: bytes) -> bytes:
        peer = await self.get_best_peer()
        return await peer.get_contract_code(block_hash, key, self.cancel_token)
