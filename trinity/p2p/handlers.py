from typing import (
    AsyncGenerator,
    List,
    Tuple,
    cast,
)

from eth_typing import BlockNumber, Hash32

from cancel_token import CancelToken

from eth.exceptions import (
    HeaderNotFound,
)
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransactionFields
from eth.tools.logging import TraceLogger

from p2p.cancellable import CancellableMixin

from trinity.db.chain import AsyncChainDB
from trinity.db.header import AsyncHeaderDB
from trinity.protocol.eth.peer import ETHPeer
from trinity.protocol.common.requests import BaseHeaderRequest
from trinity.rlp.block_body import BlockBody


class PeerRequestHandler(CancellableMixin):
    def __init__(self, db: AsyncHeaderDB, logger: TraceLogger, token: CancelToken) -> None:
        self.db = db
        self.logger = logger
        self.cancel_token = token

    async def handle_get_block_bodies(self, peer: ETHPeer, block_hashes: List[Hash32]) -> None:
        if not peer.is_operational:
            return
        self.logger.trace("%s requested bodies for %d blocks", peer, len(block_hashes))
        chaindb = cast(AsyncChainDB, self.db)
        bodies = []
        for block_hash in block_hashes:
            try:
                header = await self.wait(chaindb.coro_get_block_header_by_hash(block_hash))
            except HeaderNotFound:
                self.logger.debug("%s asked for block we don't have: %s", peer, block_hash)
                continue
            transactions = await self.wait(
                chaindb.coro_get_block_transactions(header, BaseTransactionFields))
            uncles = await self.wait(chaindb.coro_get_block_uncles(header.uncles_hash))
            bodies.append(BlockBody(transactions, uncles))
        self.logger.trace("Replying to %s with %d block bodies", peer, len(bodies))
        peer.sub_proto.send_block_bodies(bodies)

    async def handle_get_receipts(self, peer: ETHPeer, block_hashes: List[Hash32]) -> None:
        if not peer.is_operational:
            return
        self.logger.trace("%s requested receipts for %d blocks", peer, len(block_hashes))
        chaindb = cast(AsyncChainDB, self.db)
        receipts = []
        for block_hash in block_hashes:
            try:
                header = await self.wait(chaindb.coro_get_block_header_by_hash(block_hash))
            except HeaderNotFound:
                self.logger.debug(
                    "%s asked receipts for block we don't have: %s", peer, block_hash)
                continue
            block_receipts = await self.wait(chaindb.coro_get_receipts(header, Receipt))
            receipts.append(block_receipts)
        self.logger.trace("Replying to %s with receipts for %d blocks", peer, len(receipts))
        peer.sub_proto.send_receipts(receipts)

    async def handle_get_node_data(self, peer: ETHPeer, node_hashes: List[Hash32]) -> None:
        if not peer.is_operational:
            return
        self.logger.trace("%s requested %d trie nodes", peer, len(node_hashes))
        chaindb = cast(AsyncChainDB, self.db)
        nodes = []
        for node_hash in node_hashes:
            try:
                node = await self.wait(chaindb.coro_get(node_hash))
            except KeyError:
                self.logger.debug("%s asked for a trie node we don't have: %s", peer, node_hash)
                continue
            nodes.append(node)
        self.logger.trace("Replying to %s with %d trie nodes", peer, len(nodes))
        peer.sub_proto.send_node_data(tuple(nodes))

    async def lookup_headers(self,
                             request: BaseHeaderRequest) -> Tuple[BlockHeader, ...]:
        """
        Lookup :max_headers: headers starting at :block_number_or_hash:, skipping :skip: items
        between each, in reverse order if :reverse: is True.
        """
        try:
            block_numbers = await self._get_block_numbers_for_request(request)
        except HeaderNotFound:
            self.logger.debug(
                "Peer requested starting header %r that is unavailable, returning nothing",
                request.block_number_or_hash)
            block_numbers = tuple()  # type: ignore

        headers: Tuple[BlockHeader, ...] = tuple([
            header
            async for header
            in self._generate_available_headers(block_numbers)
        ])
        return headers

    async def _get_block_numbers_for_request(self,
                                             request: BaseHeaderRequest,
                                             ) -> Tuple[BlockNumber, ...]:
        """
        Generate the block numbers for a given `HeaderRequest`.
        """
        if isinstance(request.block_number_or_hash, bytes):
            header = await self.wait(
                self.db.coro_get_block_header_by_hash(cast(Hash32, request.block_number_or_hash)))
            return request.generate_block_numbers(header.block_number)
        elif isinstance(request.block_number_or_hash, int):
            # We don't need to pass in the block number to
            # `generate_block_numbers` since the request is based on a numbered
            # block identifier.
            return request.generate_block_numbers()
        else:
            raise TypeError(
                "Invariant: unexpected type for 'block_number_or_hash': %s",
                type(request.block_number_or_hash),
            )

    async def _generate_available_headers(
            self, block_numbers: Tuple[BlockNumber, ...]) -> AsyncGenerator[BlockHeader, None]:
        """
        Generates the headers requested, halting on the first header that is not locally available.
        """
        for block_num in block_numbers:
            try:
                yield await self.wait(
                    self.db.coro_get_canonical_block_header_by_number(block_num))
            except HeaderNotFound:
                self.logger.debug(
                    "Peer requested header number %s that is unavailable, stopping search.",
                    block_num,
                )
                break
