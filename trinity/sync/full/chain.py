import asyncio
import math
from typing import (
    Any,
    Callable,
    Dict,
    List,
    NamedTuple,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

from cytoolz import (
    partition_all,
    unique,
)

from eth_typing import Hash32

from cancel_token import CancelToken

from eth.constants import (
    BLANK_ROOT_HASH, EMPTY_UNCLE_HASH, GENESIS_PARENT_HASH)
from eth.chains import AsyncChain
from eth.db.trie import make_trie_root_and_nodes
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransaction

from p2p import protocol
from p2p.exceptions import NoEligiblePeers
from p2p.p2p_proto import DisconnectReason
from p2p.peer import PeerPool
from p2p.protocol import Command

from trinity.db.chain import AsyncChainDB
from trinity.protocol.eth import commands
from trinity.protocol.eth import (
    constants as eth_constants,
)
from trinity.protocol.eth.peer import ETHPeer
from trinity.protocol.eth.requests import HeaderRequest
from trinity.protocol.les.peer import LESPeer
from trinity.rlp.block_body import BlockBody
from trinity.sync.common.chain import BaseHeaderChainSyncer
from trinity.utils.timer import Timer


HeaderRequestingPeer = Union[LESPeer, ETHPeer]


class FastChainSyncer(BaseHeaderChainSyncer):
    """
    Sync with the Ethereum network by fetching block headers/bodies and storing them in our DB.

    Here, the run() method returns as soon as we complete a sync with the peer that announced the
    highest TD, at which point we must run the StateDownloader to fetch the state for our chain
    head.
    """
    db: AsyncChainDB
    _exit_on_sync_complete = True

    def __init__(self,
                 chain: AsyncChain,
                 db: AsyncChainDB,
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(chain, db, peer_pool, token)
        # Those are used by our msg handlers and _download_block_parts() in order to track missing
        # bodies/receipts for a given chain segment.
        self._downloaded_receipts: asyncio.Queue[Tuple[ETHPeer, List[DownloadedBlockPart]]] = asyncio.Queue()  # noqa: E501
        self._downloaded_bodies: asyncio.Queue[Tuple[ETHPeer, List[DownloadedBlockPart]]] = asyncio.Queue()  # noqa: E501

    subscription_msg_types: Set[Type[Command]] = {
        commands.BlockBodies,
        commands.Receipts,
        commands.NewBlock,
        commands.GetBlockHeaders,
        commands.BlockHeaders,
        commands.GetBlockBodies,
        commands.GetReceipts,
        commands.GetNodeData,
        commands.Transactions,
        commands.NodeData,
        # TODO: all of the following are here to quiet warning logging output
        # until the messages are properly handled.
        commands.Transactions,
        commands.NewBlock,
        commands.NewBlockHashes,
    }

    async def _calculate_td(self, headers: Tuple[BlockHeader, ...]) -> int:
        """Return the score (total difficulty) of the last header in the given list.

        Assumes the first header's parent is already present in our DB.

        Used when we have a batch of headers that has not been persisted to the DB yet, and we
        need to know the score for the last one of them.
        """
        if headers[0].parent_hash == GENESIS_PARENT_HASH:
            td = 0
        else:
            td = await self.wait(self.db.coro_get_score(headers[0].parent_hash))
        for header in headers:
            td += header.difficulty
        return td

    async def _process_headers(
            self, peer: HeaderRequestingPeer, headers: Tuple[BlockHeader, ...]) -> int:
        timer = Timer()
        target_td = await self._calculate_td(headers)
        bodies = await self._download_block_parts(
            target_td,
            [header for header in headers if not _is_body_empty(header)],
            self.request_bodies,
            self._downloaded_bodies,
            _body_key,
            'body')
        self.logger.debug("Got block bodies for chain segment")

        missing_receipts = [header for header in headers if not _is_receipts_empty(header)]
        # Post-Byzantium blocks may have identical receipt roots (e.g. when they have the same
        # number of transactions and all succeed/failed: ropsten blocks 2503212 and 2503284),
        # so we do this to avoid requesting the same receipts multiple times.
        missing_receipts = list(unique(missing_receipts, key=_receipts_key))
        await self._download_block_parts(
            target_td,
            missing_receipts,
            self.request_receipts,
            self._downloaded_receipts,
            _receipts_key,
            'receipt')
        self.logger.debug("Got block receipts for chain segment")

        for header in headers:
            if header.uncles_hash != EMPTY_UNCLE_HASH:
                body = cast(BlockBody, bodies[_body_key(header)])
                uncles = body.uncles
            else:
                uncles = tuple()
            vm_class = self.chain.get_vm_class_for_block_number(header.block_number)
            block_class = vm_class.get_block_class()
            # We don't need to use our block transactions here because persist_block() doesn't do
            # anything with them as it expects them to have been persisted already.
            block = block_class(header, uncles=uncles)
            await self.wait(self.db.coro_persist_block(block))

        head = await self.wait(self.db.coro_get_canonical_head())
        txs = sum(len(cast(BlockBody, body).transactions) for body in bodies.values())
        self.logger.info(
            "Imported %d blocks (%d txs) in %0.2f seconds, new head: #%d",
            len(headers), txs, timer.elapsed, head.block_number)
        return head.block_number

    async def _download_block_parts(
            self,
            target_td: int,
            headers: List[BlockHeader],
            request_func: Callable[[int, List[BlockHeader]], int],
            download_queue: 'asyncio.Queue[Tuple[ETHPeer, List[DownloadedBlockPart]]]',
            key_func: Callable[[BlockHeader], Union[bytes, Tuple[bytes, bytes]]],
            part_name: str
    ) -> 'Dict[Union[bytes, Tuple[bytes, bytes]], Union[BlockBody, List[Receipt]]]':
        """Download block parts for the given headers, using the given request_func.

        Retry timed out parts until we have the parts for all headers.

        Raises NoEligiblePeers if at any moment we have no connected peers that have the blocks
        we want.
        """
        missing = headers.copy()
        # The ETH protocol doesn't guarantee that we'll get all body parts requested, so we need
        # to keep track of the number of pending replies and missing items to decide when to retry
        # them. See request_receipts() for more info.
        pending_replies = request_func(target_td, missing)
        parts: List[DownloadedBlockPart] = []
        while missing:
            if pending_replies == 0:
                pending_replies = request_func(target_td, missing)

            try:
                peer, received = await self.wait(
                    download_queue.get(),
                    timeout=self._reply_timeout)
            except TimeoutError:
                self.logger.info(
                    "Timed out waiting for %d missing %s", len(missing), part_name)
                pending_replies = request_func(target_td, missing)
                continue

            received_keys = set([part.unique_key for part in received])

            duplicates = received_keys.intersection(part.unique_key for part in parts)
            unexpected = received_keys.difference(key_func(header) for header in headers)

            parts.extend(received)
            pending_replies -= 1

            if unexpected:
                self.logger.debug("Got %d unexpected %s from %s", len(unexpected), part_name, peer)
            if duplicates:
                self.logger.debug("Got %d duplicate %s from %s", len(duplicates), part_name, peer)

            missing = [
                header
                for header in missing
                if key_func(header) not in received_keys
            ]

        return dict((part.unique_key, part.part) for part in parts)

    def _request_block_parts(
            self,
            target_td: int,
            headers: List[BlockHeader],
            request_func: Callable[[ETHPeer, List[BlockHeader]], None]) -> int:
        peers = self.peer_pool.get_peers(target_td)
        if not peers:
            raise NoEligiblePeers()
        length = math.ceil(len(headers) / len(peers))
        batches = list(partition_all(length, headers))
        for peer, batch in zip(peers, batches):
            request_func(cast(ETHPeer, peer), batch)
        return len(batches)

    def _send_get_block_bodies(self, peer: ETHPeer, headers: List[BlockHeader]) -> None:
        block_numbers = ", ".join(str(h.block_number) for h in headers)
        self.logger.debug(
            "Requesting %d block bodies (%s) to %s", len(headers), block_numbers, peer)
        peer.sub_proto.send_get_block_bodies([header.hash for header in headers])

    def _send_get_receipts(self, peer: ETHPeer, headers: List[BlockHeader]) -> None:
        block_numbers = ", ".join(str(h.block_number) for h in headers)
        self.logger.debug(
            "Requesting %d block receipts (%s) to %s", len(headers), block_numbers, peer)
        peer.sub_proto.send_get_receipts([header.hash for header in headers])

    def request_bodies(self, target_td: int, headers: List[BlockHeader]) -> int:
        """Ask our peers for bodies for the given headers.

        See request_receipts() for details of how this is done.
        """
        return self._request_block_parts(target_td, headers, self._send_get_block_bodies)

    def request_receipts(self, target_td: int, headers: List[BlockHeader]) -> int:
        """Ask our peers for receipts for the given headers.

        We partition the given list of headers in batches and request each to one of our connected
        peers. This is done because geth enforces a byte-size cap when replying to a GetReceipts
        msg, and we then need to re-request the items that didn't fit, so by splitting the
        requests across all our peers we reduce the likelyhood of having to make multiple
        serialized requests to ask for missing items (which happens quite frequently in practice).

        Returns the number of requests made.
        """
        return self._request_block_parts(target_td, headers, self._send_get_receipts)

    async def _handle_msg(self, peer: HeaderRequestingPeer, cmd: protocol.Command,
                          msg: protocol._DecodedMsgType) -> None:
        peer = cast(ETHPeer, peer)

        # TODO: stop ignoring these once we have proper handling for these messages.
        ignored_commands = (commands.Transactions, commands.NewBlock, commands.NewBlockHashes)

        if isinstance(cmd, ignored_commands):
            pass
        elif isinstance(cmd, commands.BlockBodies):
            await self._handle_block_bodies(peer, list(cast(Tuple[BlockBody], msg)))
        elif isinstance(cmd, commands.Receipts):
            await self._handle_block_receipts(peer, cast(List[List[Receipt]], msg))
        elif isinstance(cmd, commands.NewBlock):
            await self._handle_new_block(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, commands.GetBlockHeaders):
            await self._handle_get_block_headers(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, commands.BlockHeaders):
            # `BlockHeaders` messages are handled at the peer level.
            pass
        elif isinstance(cmd, commands.GetBlockBodies):
            # Only serve up to MAX_BODIES_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:eth_constants.MAX_BODIES_FETCH]
            await self._handler.handle_get_block_bodies(peer, block_hashes)
        elif isinstance(cmd, commands.GetReceipts):
            # Only serve up to MAX_RECEIPTS_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:eth_constants.MAX_RECEIPTS_FETCH]
            await self._handler.handle_get_receipts(peer, block_hashes)
        elif isinstance(cmd, commands.GetNodeData):
            # Only serve up to MAX_STATE_FETCH items in every request.
            node_hashes = cast(List[Hash32], msg)[:eth_constants.MAX_STATE_FETCH]
            await self._handler.handle_get_node_data(peer, node_hashes)
        elif isinstance(cmd, commands.Transactions):
            # Transactions msgs are handled by our TxPool service.
            pass
        elif isinstance(cmd, commands.NodeData):
            # When doing a chain sync we never send GetNodeData requests, so peers should not send
            # us NodeData msgs.
            self.logger.warn("Unexpected NodeData msg from %s, disconnecting", peer)
            await peer.disconnect(DisconnectReason.bad_protocol)
        else:
            self.logger.debug("%s msg not handled yet, need to be implemented", cmd)

    async def _handle_new_block(self, peer: ETHPeer, msg: Dict[str, Any]) -> None:
        self._sync_requests.put_nowait(peer)

    async def _handle_block_receipts(self,
                                     peer: ETHPeer,
                                     receipts_by_block: List[List[Receipt]]) -> None:
        self.logger.debug("Got Receipts for %d blocks from %s", len(receipts_by_block), peer)
        iterator = map(make_trie_root_and_nodes, receipts_by_block)
        # The map() call above is lazy (it returns an iterator! ;-), so it's only evaluated in
        # the executor when the list() is applied to it.
        receipts_tries = await self._run_in_executor(list, iterator)
        downloaded: List[DownloadedBlockPart] = []
        # TODO: figure out why mypy is losing the type of the receipts_tries
        # so we can get rid of the ignore
        for (receipts, (receipt_root, trie_dict_data)) in zip(receipts_by_block, receipts_tries):  # type: ignore # noqa: E501
            await self.wait(self.db.coro_persist_trie_data_dict(trie_dict_data))
            downloaded.append(DownloadedBlockPart(receipts, receipt_root))
        self._downloaded_receipts.put_nowait((peer, downloaded))

    async def _handle_block_bodies(self,
                                   peer: ETHPeer,
                                   bodies: List[BlockBody]) -> None:
        self.logger.debug("Got Bodies for %d blocks from %s", len(bodies), peer)
        iterator = map(make_trie_root_and_nodes, [body.transactions for body in bodies])
        # The map() call above is lazy (it returns an iterator! ;-), so it's only evaluated in
        # the executor when the list() is applied to it.
        transactions_tries = await self._run_in_executor(list, iterator)
        downloaded: List[DownloadedBlockPart] = []

        # TODO: figure out why mypy is losing the type of the transactions_tries
        # so we can get rid of the ignore
        for (body, (tx_root, trie_dict_data)) in zip(bodies, transactions_tries):  # type: ignore
            await self.wait(self.db.coro_persist_trie_data_dict(trie_dict_data))
            uncles_hash = await self.wait(self.db.coro_persist_uncles(body.uncles))
            downloaded.append(DownloadedBlockPart(body, (tx_root, uncles_hash)))
        self._downloaded_bodies.put_nowait((peer, downloaded))

    async def _handle_get_block_headers(
            self,
            peer: ETHPeer,
            query: Dict[str, Any]) -> None:
        self.logger.debug("Peer %s made header request: %s", peer, query)
        request = HeaderRequest(
            query['block_number_or_hash'],
            query['max_headers'],
            query['skip'],
            query['reverse'],
        )

        headers = await self._handler.lookup_headers(request)
        self.logger.trace("Replying to %s with %d headers", peer, len(headers))
        peer.sub_proto.send_block_headers(headers)


class RegularChainSyncer(FastChainSyncer):
    """
    Sync with the Ethereum network by fetching block headers/bodies and importing them.

    Here, the run() method will execute the sync loop forever, until our CancelToken is triggered.
    """
    _exit_on_sync_complete = False
    _seal_check_random_sample_rate = 1

    async def _handle_block_receipts(
            self, peer: ETHPeer, receipts_by_block: List[List[Receipt]]) -> None:
        # When doing a regular sync we never request receipts.
        self.logger.warn("Unexpected BlockReceipts msg from %s, disconnecting", peer)
        await peer.disconnect(DisconnectReason.bad_protocol)

    async def _process_headers(
            self, peer: HeaderRequestingPeer, headers: Tuple[BlockHeader, ...]) -> int:
        target_td = await self._calculate_td(headers)
        downloaded_parts = await self._download_block_parts(
            target_td,
            [header for header in headers if not _is_body_empty(header)],
            self.request_bodies,
            self._downloaded_bodies,
            _body_key,
            'body')
        self.logger.info("Got block bodies for chain segment")

        for header in headers:
            vm_class = self.chain.get_vm_class_for_block_number(header.block_number)
            block_class = vm_class.get_block_class()

            if _is_body_empty(header):
                transactions: List[BaseTransaction] = []
                uncles: List[BlockHeader] = []
            else:
                body = cast(BlockBody, downloaded_parts[_body_key(header)])
                tx_class = block_class.get_transaction_class()
                transactions = [tx_class.from_base_transaction(tx)
                                for tx in body.transactions]
                uncles = body.uncles

            block = block_class(header, transactions, uncles)
            timer = Timer()
            await self.wait(self.chain.coro_import_block(block, perform_validation=True))
            self.logger.info("Imported block %d (%d txs) in %f seconds",
                             block.number, len(transactions), timer.elapsed)

        head = await self.wait(self.db.coro_get_canonical_head())
        self.logger.info("Imported chain segment, new head: #%d", head.block_number)
        return head.block_number


class DownloadedBlockPart(NamedTuple):
    part: Union[BlockBody, List[Receipt]]
    unique_key: Union[bytes, Tuple[bytes, bytes]]


def _body_key(header: BlockHeader) -> Tuple[bytes, bytes]:
    """Return the unique key of the body for the given header.

    i.e. a two-tuple with the transaction root and uncles hash.
    """
    return cast(Tuple[bytes, bytes], (header.transaction_root, header.uncles_hash))


def _receipts_key(header: BlockHeader) -> bytes:
    """Return the unique key of the list of receipts for the given header.

    i.e. the header's receipt root.
    """
    return header.receipt_root


def _is_body_empty(header: BlockHeader) -> bool:
    return header.transaction_root == BLANK_ROOT_HASH and header.uncles_hash == EMPTY_UNCLE_HASH


def _is_receipts_empty(header: BlockHeader) -> bool:
    return header.receipt_root == BLANK_ROOT_HASH
