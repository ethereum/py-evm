from typing import (
    Any,
    Dict,
    Set,
    Sequence,
    Type,
    Union,
    cast,
)

from cancel_token import CancelToken

from eth.exceptions import (
    HeaderNotFound,
)
from eth_typing import (
    BlockIdentifier,
    Hash32,
)

from p2p import protocol
from p2p.peer import BasePeer
from p2p.protocol import (
    Command,
)

from trinity.db.chain import AsyncChainDB
from trinity.protocol.common.servers import BaseRequestServer, BasePeerRequestHandler
from trinity.protocol.eth import commands
from trinity.protocol.eth.peer import ETHPeer, ETHPeerPool

from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransactionFields

from trinity.protocol.eth.constants import (
    MAX_BODIES_FETCH,
    MAX_RECEIPTS_FETCH,
    MAX_STATE_FETCH,
)
from trinity.protocol.eth.requests import HeaderRequest as ETHHeaderRequest
from trinity.rlp.block_body import BlockBody


class ETHPeerRequestHandler(BasePeerRequestHandler):
    def __init__(self, db: AsyncChainDB, token: CancelToken) -> None:
        super().__init__(db, token)
        self.db: AsyncChainDB = db

    async def handle_get_block_headers(
            self,
            peer: ETHPeer,
            msg: Dict[str, Any]) -> None:
        if not peer.is_operational:
            return
        query = cast(Dict[Any, Union[bool, int]], msg)
        self.logger.debug("%s requested headers: %s", peer, query)
        request = ETHHeaderRequest(
            cast(BlockIdentifier, query['block_number_or_hash']),
            query['max_headers'],
            query['skip'],
            cast(bool, query['reverse']),
        )

        headers = await self.lookup_headers(request)
        self.logger.debug2("Replying to %s with %d headers", peer, len(headers))
        peer.sub_proto.send_block_headers(headers)

    async def handle_get_block_bodies(self, peer: ETHPeer, block_hashes: Sequence[Hash32]) -> None:
        if not peer.is_operational:
            return
        self.logger.debug2("%s requested bodies for %d blocks", peer, len(block_hashes))
        bodies = []
        # Only serve up to MAX_BODIES_FETCH items in every request.
        for block_hash in block_hashes[:MAX_BODIES_FETCH]:
            try:
                header = await self.wait(self.db.coro_get_block_header_by_hash(block_hash))
            except HeaderNotFound:
                self.logger.debug("%s asked for block we don't have: %s", peer, block_hash)
                continue
            transactions = await self.wait(
                self.db.coro_get_block_transactions(header, BaseTransactionFields))
            uncles = await self.wait(self.db.coro_get_block_uncles(header.uncles_hash))
            bodies.append(BlockBody(transactions, uncles))
        self.logger.debug2("Replying to %s with %d block bodies", peer, len(bodies))
        peer.sub_proto.send_block_bodies(bodies)

    async def handle_get_receipts(self, peer: ETHPeer, block_hashes: Sequence[Hash32]) -> None:
        if not peer.is_operational:
            return
        self.logger.debug2("%s requested receipts for %d blocks", peer, len(block_hashes))
        receipts = []
        # Only serve up to MAX_RECEIPTS_FETCH items in every request.
        for block_hash in block_hashes[:MAX_RECEIPTS_FETCH]:
            try:
                header = await self.wait(self.db.coro_get_block_header_by_hash(block_hash))
            except HeaderNotFound:
                self.logger.debug(
                    "%s asked receipts for block we don't have: %s", peer, block_hash)
                continue
            block_receipts = await self.wait(self.db.coro_get_receipts(header, Receipt))
            receipts.append(block_receipts)
        self.logger.debug2("Replying to %s with receipts for %d blocks", peer, len(receipts))
        peer.sub_proto.send_receipts(receipts)

    async def handle_get_node_data(self, peer: ETHPeer, node_hashes: Sequence[Hash32]) -> None:
        if not peer.is_operational:
            return
        self.logger.debug2("%s requested %d trie nodes", peer, len(node_hashes))
        nodes = []
        # Only serve up to MAX_STATE_FETCH items in every request.
        for node_hash in node_hashes[:MAX_STATE_FETCH]:
            try:
                node = await self.wait(self.db.coro_get(node_hash))
            except KeyError:
                self.logger.debug("%s asked for a trie node we don't have: %s", peer, node_hash)
                continue
            nodes.append(node)
        self.logger.debug2("Replying to %s with %d trie nodes", peer, len(nodes))
        peer.sub_proto.send_node_data(tuple(nodes))


class ETHRequestServer(BaseRequestServer):
    """
    Monitor commands from peers, to identify inbound requests that should receive a response.
    Handle those inbound requests by querying our local database and replying.
    """
    subscription_msg_types: Set[Type[Command]] = {
        commands.GetBlockHeaders,
        commands.GetBlockBodies,
        commands.GetReceipts,
        commands.GetNodeData,
        # TODO: all of the following are here to quiet warning logging output
        # until the messages are properly handled.
        commands.Transactions,
        commands.NewBlockHashes,
    }

    def __init__(
            self,
            db: AsyncChainDB,
            peer_pool: ETHPeerPool,
            token: CancelToken = None) -> None:
        super().__init__(peer_pool, token)
        self._handler = ETHPeerRequestHandler(db, self.cancel_token)

    async def _handle_msg(self, base_peer: BasePeer, cmd: Command,
                          msg: protocol._DecodedMsgType) -> None:
        peer = cast(ETHPeer, base_peer)

        ignored_commands = (
            commands.Transactions,
            commands.NewBlockHashes,
        )

        if isinstance(cmd, ignored_commands):
            pass
        elif isinstance(cmd, commands.GetBlockHeaders):
            await self._handler.handle_get_block_headers(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, commands.GetBlockBodies):
            block_hashes = cast(Sequence[Hash32], msg)
            await self._handler.handle_get_block_bodies(peer, block_hashes)
        elif isinstance(cmd, commands.GetReceipts):
            block_hashes = cast(Sequence[Hash32], msg)
            await self._handler.handle_get_receipts(peer, block_hashes)
        elif isinstance(cmd, commands.GetNodeData):
            node_hashes = cast(Sequence[Hash32], msg)
            await self._handler.handle_get_node_data(peer, node_hashes)
        else:
            self.logger.debug("%s msg not handled yet, need to be implemented", cmd)
