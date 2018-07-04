import asyncio
import logging
import math
import time
from abc import abstractmethod
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    NamedTuple,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
    cast,
)

from cytoolz import (
    partition_all,
    unique,
)

from eth_typing import BlockNumber, Hash32

from evm.constants import (
    BLANK_ROOT_HASH, EMPTY_UNCLE_HASH, GENESIS_BLOCK_NUMBER, GENESIS_PARENT_HASH)
from evm.chains import AsyncChain
from evm.db.trie import make_trie_root_and_nodes
from evm.exceptions import HeaderNotFound, ValidationError
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt
from evm.rlp.transactions import BaseTransaction, BaseTransactionFields

from p2p import protocol
from p2p import eth
from p2p import les
from p2p.cancel_token import CancelToken, wait_with_token
from p2p.constants import MAX_REORG_DEPTH
from p2p.exceptions import NoEligiblePeers, OperationCancelled
from p2p.peer import BasePeer, ETHPeer, LESPeer, PeerPool, PeerPoolSubscriber
from p2p.rlp import BlockBody
from p2p.service import BaseService
from p2p.utils import (
    get_process_pool_executor,
)


if TYPE_CHECKING:
    from trinity.db.chain import AsyncChainDB  # noqa: F401
    from trinity.db.header import AsyncHeaderDB  # noqa: F401


HeaderRequestingPeer = Union[LESPeer, ETHPeer]


class BaseHeaderChainSyncer(BaseService, PeerPoolSubscriber):
    """
    Sync with the Ethereum network by fetching/storing block headers.

    Here, the run() method will execute the sync loop until our local head is the same as the one
    with the highest TD announced by any of our peers.
    """
    # We'll only sync if we are connected to at least min_peers_to_sync.
    min_peers_to_sync = 1
    # Should we exit upon completing a sync with a given peer?
    _exit_on_sync_complete = False
    # TODO: Instead of a fixed timeout, we should use a variable one that gets adjusted based on
    # the round-trip times from our download requests.
    _reply_timeout = 60

    def __init__(self,
                 chain: AsyncChain,
                 db: 'AsyncHeaderDB',
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.db = db
        self.peer_pool = peer_pool
        self._syncing = False
        self._sync_complete = asyncio.Event()
        self._sync_requests: asyncio.Queue[HeaderRequestingPeer] = asyncio.Queue()
        self._new_headers: asyncio.Queue[Tuple[BlockHeader, ...]] = asyncio.Queue()
        self._executor = get_process_pool_executor()

    def register_peer(self, peer: BasePeer) -> None:
        self._sync_requests.put_nowait(cast(HeaderRequestingPeer, self.peer_pool.highest_td_peer))

    async def _handle_msg_loop(self) -> None:
        while self.is_running:
            try:
                peer, cmd, msg = await self.wait(self.msg_queue.get())
            except OperationCancelled:
                break

            # Our handle_msg() method runs cpu-intensive tasks in sub-processes so that the main
            # loop can keep processing msgs, and that's why we use ensure_future() instead of
            # awaiting for it to finish here.
            asyncio.ensure_future(self.handle_msg(cast(HeaderRequestingPeer, peer), cmd, msg))

    async def handle_msg(self, peer: HeaderRequestingPeer, cmd: protocol.Command,
                         msg: protocol._DecodedMsgType) -> None:
        try:
            await self._handle_msg(peer, cmd, msg)
        except OperationCancelled:
            # Silently swallow OperationCancelled exceptions because we run unsupervised (i.e.
            # with ensure_future()). Our caller will also get an OperationCancelled anyway, and
            # there it will be handled.
            pass
        except Exception:
            self.logger.exception("Unexpected error when processing msg from %s", peer)

    async def _run(self) -> None:
        asyncio.ensure_future(self._handle_msg_loop())
        with self.subscribe(self.peer_pool):
            while True:
                peer_or_finished = await self.wait_first(
                    self._sync_requests.get(), self._sync_complete.wait())  # type: Any

                # In the case of a fast sync, we return once the sync is completed, and our caller
                # must then run the StateDownloader.
                if self._sync_complete.is_set():
                    return

                # Since self._sync_complete is not set, peer_or_finished can only be a Peer
                # instance.
                asyncio.ensure_future(self.sync(peer_or_finished))

    async def _cleanup(self) -> None:
        # We don't need to cancel() anything, but we yield control just so that the coroutines we
        # run in the background notice the cancel token has been triggered and return.
        await asyncio.sleep(0)

    async def sync(self, peer: HeaderRequestingPeer) -> None:
        if self._syncing:
            self.logger.debug(
                "Got a NewBlock or a new peer, but already syncing so doing nothing")
            return
        elif len(self.peer_pool) < self.min_peers_to_sync:
            self.logger.info(
                "Connected to less peers (%d) than the minimum (%d) required to sync, "
                "doing nothing", len(self.peer_pool), self.min_peers_to_sync)
            return

        self._syncing = True
        try:
            await self._sync(peer)
        except OperationCancelled as e:
            self.logger.info("Sync with %s aborted: %s", peer, e)
        finally:
            self._syncing = False

    async def _sync(self, peer: HeaderRequestingPeer) -> None:
        """Try to fetch/process blocks until the given peer's head_hash.

        Returns when the peer's head_hash is available in our ChainDB, or if any error occurs
        during the sync.

        If in fast-sync mode, the _sync_completed event will be set upon successful completion of
        a sync.
        """
        head = await self.wait(self.db.coro_get_canonical_head())
        head_td = await self.wait(self.db.coro_get_score(head.hash))
        if peer.head_td <= head_td:
            self.logger.info(
                "Head TD (%d) announced by %s not higher than ours (%d), not syncing",
                peer.head_td, peer, head_td)
            return

        self.logger.info("Starting sync with %s", peer)
        # When we start the sync with a peer, we always request up to MAX_REORG_DEPTH extra
        # headers before our current head's number, in case there were chain reorgs since the last
        # time _sync() was called. All of the extra headers that are already present in our DB
        # will be discarded by _fetch_missing_headers() so we don't unnecessarily process them
        # again.
        start_at = max(GENESIS_BLOCK_NUMBER + 1, head.block_number - MAX_REORG_DEPTH)
        while True:
            if not peer.is_running:
                self.logger.info("%s disconnected, aborting sync", peer)
                break

            try:
                headers = await self._fetch_missing_headers(peer, start_at)
            except TimeoutError:
                self.logger.warn("Timeout waiting for header batch from %s, aborting sync", peer)
                await peer.cancel()
                break

            if not headers:
                self.logger.info("Got no new headers from %s, aborting sync", peer)
                break

            first = headers[0]
            try:
                await self.wait(self.db.coro_get_block_header_by_hash(first.parent_hash))
            except HeaderNotFound:
                self.logger.warn("Unable to find common ancestor betwen our chain and %s", peer)
                break

            self.logger.debug("Got new header chain starting at #%d", first.block_number)
            start = time.time()
            try:
                await self.chain.coro_validate_chain(headers)
            except ValidationError as e:
                self.logger.warn("Received invalid headers from %s, aborting sync: %s", peer, e)
                break
            try:
                head_number = await self._process_headers(peer, headers)
            except NoEligiblePeers:
                self.logger.info("No peers have the blocks we want, aborting sync")
                break
            self.logger.info(
                "Imported %d headers in %0.2f seconds, new head: #%d",
                len(headers), time.time() - start, head_number)
            start_at = head_number + 1

            # Quite often the header batch we receive here includes headers past the peer's reported
            # head (via the NewBlock msg), so we can't compare our head's hash to the peer's in
            # order to see if the sync is completed. Instead we just check that we have the peer's
            # head_hash in our chain.
            if await self.wait(self.db.coro_header_exists(peer.head_hash)):
                self.logger.info("Sync with %s completed", peer)
                if self._exit_on_sync_complete:
                    self._sync_complete.set()
                break

    async def _fetch_missing_headers(
            self, peer: HeaderRequestingPeer, start_at: int) -> Tuple[BlockHeader, ...]:
        """Fetch a batch of headers starting at start_at and return the ones we're missing."""
        self.logger.debug("Fetching chain segment starting at #%d", start_at)
        peer.request_block_headers(start_at, peer.max_headers_fetch, reverse=False)
        # Pass the peer's token to self.wait() because we want to abort if either we
        # or the peer terminates.
        headers = list(await self.wait(
            self._new_headers.get(),
            token=peer.cancel_token,
            timeout=self._reply_timeout))
        for header in headers.copy():
            try:
                await self.wait(self.db.coro_get_block_header_by_hash(header.hash))
            except HeaderNotFound:
                break
            else:
                self.logger.debug("Discarding %s as we already have it", header)
                headers.remove(header)
        return tuple(headers)

    def _handle_block_headers(self, headers: Tuple[BlockHeader, ...]) -> None:
        if not headers:
            self.logger.warn("Got an empty BlockHeaders msg")
            return
        self.logger.debug(
            "Got BlockHeaders from %d to %d", headers[0].block_number, headers[-1].block_number)
        self._new_headers.put_nowait(headers)

    @abstractmethod
    async def _handle_msg(self, peer: HeaderRequestingPeer, cmd: protocol.Command,
                          msg: protocol._DecodedMsgType) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    async def _process_headers(
            self, peer: HeaderRequestingPeer, headers: Tuple[BlockHeader, ...]) -> int:
        raise NotImplementedError("Must be implemented by subclasses")


class LightChainSyncer(BaseHeaderChainSyncer):
    _exit_on_sync_complete = False

    async def _handle_msg(self, peer: HeaderRequestingPeer, cmd: protocol.Command,
                          msg: protocol._DecodedMsgType) -> None:
        if isinstance(cmd, les.Announce):
            self._sync_requests.put_nowait(peer)
        elif isinstance(cmd, les.BlockHeaders):
            msg = cast(Dict[str, Any], msg)
            self._handle_block_headers(tuple(cast(Tuple[BlockHeader, ...], msg['headers'])))
        elif isinstance(cmd, les.GetBlockHeaders):
            msg = cast(Dict[str, Any], msg)
            await self._handle_get_block_headers(cast(LESPeer, peer), msg)
        else:
            self.logger.debug("Ignoring %s message from %s", cmd, peer)

    async def _handle_get_block_headers(self, peer: LESPeer, msg: Dict[str, Any]) -> None:
        self.logger.debug("Peer %s made header request: %s", peer, msg)
        query = msg['query']
        headers = await lookup_headers(
            self.db, query.block_number_or_hash, query.max_headers,
            query.skip, query.reverse, self.logger, self.cancel_token)
        peer.sub_proto.send_block_headers(headers, buffer_value=0, request_id=msg['request_id'])

    async def _process_headers(
            self, peer: HeaderRequestingPeer, headers: Tuple[BlockHeader, ...]) -> int:
        for header in headers:
            await self.wait(self.db.coro_persist_header(header))

        head = await self.wait(self.db.coro_get_canonical_head())
        return head.block_number


class FastChainSyncer(BaseHeaderChainSyncer):
    """
    Sync with the Ethereum network by fetching block headers/bodies and storing them in our DB.

    Here, the run() method returns as soon as we complete a sync with the peer that announced the
    highest TD, at which point we must run the StateDownloader to fetch the state for our chain
    head.
    """
    db: 'AsyncChainDB'
    _exit_on_sync_complete = True

    def __init__(self,
                 chain: AsyncChain,
                 db: 'AsyncChainDB',
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(chain, db, peer_pool, token)
        # Those are used by our msg handlers and _download_block_parts() in order to track missing
        # bodies/receipts for a given chain segment.
        self._downloaded_receipts: asyncio.Queue[Tuple[ETHPeer, List[DownloadedBlockPart]]] = asyncio.Queue()  # noqa: E501
        self._downloaded_bodies: asyncio.Queue[Tuple[ETHPeer, List[DownloadedBlockPart]]] = asyncio.Queue()  # noqa: E501

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
                pending_replies = request_func(target_td, missing)
                continue

            received_keys = set([part.unique_key for part in received])

            duplicates = received_keys.intersection(part.unique_key for part in parts)
            unexpected = received_keys.difference(key_func(header) for header in headers)

            parts.extend(received)
            pending_replies -= 1

            if unexpected:
                self.logger.debug("Got unexpected %s from %s: %s", part_name, peer, unexpected)
            if duplicates:
                self.logger.debug("Got duplicate %s from %s: %s", part_name, peer, duplicates)

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
        self.logger.debug("Requesting %d block bodies to %s", len(headers), peer)
        peer.sub_proto.send_get_block_bodies([header.hash for header in headers])

    def _send_get_receipts(self, peer: ETHPeer, headers: List[BlockHeader]) -> None:
        self.logger.debug("Requesting %d block receipts to %s", len(headers), peer)
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
        if isinstance(cmd, eth.BlockHeaders):
            self._handle_block_headers(tuple(cast(Tuple[BlockHeader, ...], msg)))
        elif isinstance(cmd, eth.BlockBodies):
            await self._handle_block_bodies(peer, list(cast(Tuple[BlockBody], msg)))
        elif isinstance(cmd, eth.Receipts):
            await self._handle_block_receipts(peer, cast(List[List[Receipt]], msg))
        elif isinstance(cmd, eth.NewBlock):
            await self._handle_new_block(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, eth.GetBlockHeaders):
            await self._handle_get_block_headers(peer, cast(Dict[str, Any], msg))
        else:
            self.logger.debug("Ignoring %s message from %s", cmd, peer)

    async def _handle_new_block(self, peer: ETHPeer, msg: Dict[str, Any]) -> None:
        self._sync_requests.put_nowait(peer)

    async def _handle_block_receipts(self,
                                     peer: ETHPeer,
                                     receipts_by_block: List[List[eth.Receipt]]) -> None:
        self.logger.debug("Got Receipts for %d blocks from %s", len(receipts_by_block), peer)
        loop = asyncio.get_event_loop()
        iterator = map(make_trie_root_and_nodes, receipts_by_block)
        # The map() call above is lazy (it returns an iterator! ;-), so it's only evaluated in
        # the executor when the list() is applied to it.
        receipts_tries = await self.wait(loop.run_in_executor(self._executor, list, iterator))
        downloaded: List[DownloadedBlockPart] = []
        # TODO: figure out why mypy is losing the type of the receipts_tries
        # so we can get rid of the ignore
        for (receipts, (receipt_root, trie_dict_data)) in zip(receipts_by_block, receipts_tries):  # type: ignore # noqa: E501
            await self.wait(self.db.coro_persist_trie_data_dict(trie_dict_data))
            downloaded.append(DownloadedBlockPart(receipts, receipt_root))
        self._downloaded_receipts.put_nowait((peer, downloaded))

    async def _handle_block_bodies(self,
                                   peer: ETHPeer,
                                   bodies: List[eth.BlockBody]) -> None:
        self.logger.debug("Got Bodies for %d blocks from %s", len(bodies), peer)
        loop = asyncio.get_event_loop()
        iterator = map(make_trie_root_and_nodes, [body.transactions for body in bodies])
        # The map() call above is lazy (it returns an iterator! ;-), so it's only evaluated in
        # the executor when the list() is applied to it.
        transactions_tries = await self.wait(
            loop.run_in_executor(self._executor, list, iterator))
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
            header_request: Dict[str, Any]) -> None:
        self.logger.debug("Peer %s made header request: %s", peer, header_request)

        headers = await lookup_headers(
            self.db, header_request['block_number_or_hash'], header_request['max_headers'],
            header_request['skip'], header_request['reverse'], self.logger, self.cancel_token)
        peer.sub_proto.send_block_headers(headers)


class RegularChainSyncer(FastChainSyncer):
    """
    Sync with the Ethereum network by fetching block headers/bodies and importing them.

    Here, the run() method will execute the sync loop forever, until our CancelToken is triggered.
    """
    _exit_on_sync_complete = False

    async def _handle_msg(self, peer: HeaderRequestingPeer, cmd: protocol.Command,
                          msg: protocol._DecodedMsgType) -> None:
        peer = cast(ETHPeer, peer)
        if isinstance(cmd, eth.BlockHeaders):
            self._handle_block_headers(tuple(cast(Tuple[BlockHeader, ...], msg)))
        elif isinstance(cmd, eth.BlockBodies):
            await self._handle_block_bodies(peer, list(cast(Tuple[eth.BlockBody], msg)))
        elif isinstance(cmd, eth.NewBlock):
            await self._handle_new_block(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, eth.GetBlockHeaders):
            await self._handle_get_block_headers(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, eth.GetBlockBodies):
            await handle_get_block_bodies(
                self.db, peer, cast(List[Hash32], msg), self.logger, self.cancel_token)
        elif isinstance(cmd, eth.GetReceipts):
            await handle_get_receipts(
                self.db, peer, cast(List[Hash32], msg), self.logger, self.cancel_token)
        elif isinstance(cmd, eth.GetNodeData):
            await handle_get_node_data(
                self.db, peer, cast(List[Hash32], msg), self.logger, self.cancel_token)
        else:
            self.logger.debug("%s msg not handled yet, need to be implemented", cmd)

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
                body = cast(eth.BlockBody, downloaded_parts[_body_key(header)])
                tx_class = block_class.get_transaction_class()
                transactions = [tx_class.from_base_transaction(tx)
                                for tx in body.transactions]
                uncles = body.uncles

            block = block_class(header, transactions, uncles)
            t = time.time()
            await self.wait(self.chain.coro_import_block(block, perform_validation=True))
            self.logger.info("Imported block %d (%d txs) in %f seconds",
                             block.number, len(transactions), time.time() - t)

        head = await self.wait(self.db.coro_get_canonical_head())
        self.logger.info("Imported chain segment, new head: #%d", head.block_number)
        return head.block_number


class DownloadedBlockPart(NamedTuple):
    part: Union[eth.BlockBody, List[Receipt]]
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


async def _get_block_numbers_for_request(
        headerdb: 'AsyncHeaderDB', block_number_or_hash: Union[int, bytes], max_headers: int,
        skip: int, reverse: bool, token: CancelToken) -> List[BlockNumber]:
    """
    Generates the block numbers requested, subject to local availability.
    """
    block_number_or_hash = block_number_or_hash
    if isinstance(block_number_or_hash, bytes):
        header = await wait_with_token(
            headerdb.coro_get_block_header_by_hash(cast(Hash32, block_number_or_hash)),
            token=token,
        )
        block_number = header.block_number
    elif isinstance(block_number_or_hash, int):
        block_number = block_number_or_hash
    else:
        raise TypeError(
            "Unexpected type for 'block_number_or_hash': %s",
            type(block_number_or_hash),
        )

    limit = max(max_headers, eth.MAX_HEADERS_FETCH)
    step = skip + 1
    if reverse:
        low = max(0, block_number - limit)
        high = block_number + 1
        block_numbers = reversed(range(low, high, step))
    else:
        low = block_number
        high = block_number + limit
        block_numbers = iter(range(low, high, step))  # mypy thinks range isn't iterable
    return list(block_numbers)


async def _generate_available_headers(
        headerdb: 'AsyncHeaderDB',
        block_numbers: List[BlockNumber],
        logger: logging.Logger,
        token: CancelToken) -> AsyncGenerator[BlockHeader, None]:
    """
    Generates the headers requested, halting on the first header that is not locally available.
    """
    for block_num in block_numbers:
        try:
            yield await wait_with_token(
                headerdb.coro_get_canonical_block_header_by_number(block_num),
                token=token
            )
        except HeaderNotFound:
            logger.debug(
                "Peer requested header number %s that is unavailable, stopping search.",
                block_num,
            )
            break


async def lookup_headers(
        headerdb: 'AsyncHeaderDB', block_number_or_hash: Union[int, bytes], max_headers: int,
        skip: int, reverse: bool, logger: logging.Logger, token: CancelToken) -> List[BlockHeader]:
    """
    Lookup :max_headers: headers starting at :block_number_or_hash:, skipping :skip: items between
    each, in reverse order if :reverse: is True.
    """
    try:
        block_numbers = await _get_block_numbers_for_request(
            headerdb, block_number_or_hash, max_headers, skip, reverse, token)
    except HeaderNotFound:
        logger.debug(
            "Peer requested starting header %r that is unavailable, returning nothing",
            block_number_or_hash)
        block_numbers = []

    headers = [header async for header in _generate_available_headers(
        headerdb, block_numbers, logger, token)]
    return headers


async def handle_get_block_bodies(
        chaindb: 'AsyncChainDB', peer: ETHPeer, block_hashes: List[Hash32],
        logger: logging.Logger, token: CancelToken) -> None:
    bodies = []
    # Only serve up to eth.MAX_BODIES_FETCH items in every request.
    for block_hash in block_hashes[:eth.MAX_BODIES_FETCH]:
        try:
            header = await wait_with_token(
                chaindb.coro_get_block_header_by_hash(block_hash),
                token=token)
        except HeaderNotFound:
            logger.debug("%s asked for block we don't have: %s", peer, block_hash)
            continue
        transactions = await wait_with_token(
            chaindb.coro_get_block_transactions(header, BaseTransactionFields),
            token=token)
        uncles = await wait_with_token(
            chaindb.coro_get_block_uncles(header.uncles_hash),
            token=token)
        bodies.append(BlockBody(transactions, uncles))
    peer.sub_proto.send_block_bodies(bodies)


async def handle_get_receipts(
        chaindb: 'AsyncChainDB', peer: ETHPeer, block_hashes: List[Hash32],
        logger: logging.Logger, token: CancelToken) -> None:
    receipts = []
    # Only serve up to eth.MAX_RECEIPTS_FETCH items in every request.
    for block_hash in block_hashes[:eth.MAX_RECEIPTS_FETCH]:
        try:
            header = await wait_with_token(
                chaindb.coro_get_block_header_by_hash(block_hash),
                token=token)
        except HeaderNotFound:
            logger.debug(
                "%s asked receipts for block we don't have: %s", peer, block_hash)
            continue
        block_receipts = await wait_with_token(
            chaindb.coro_get_receipts(header, Receipt),
            token=token)
        receipts.append(block_receipts)
    peer.sub_proto.send_receipts(receipts)


async def handle_get_node_data(
        chaindb: 'AsyncChainDB', peer: ETHPeer, node_hashes: List[Hash32],
        logger: logging.Logger, token: CancelToken) -> None:
    nodes = []
    # Only serve up to eth.MAX_STATE_FETCH items in every request.
    for node_hash in node_hashes[:eth.MAX_STATE_FETCH]:
        try:
            node = await wait_with_token(
                chaindb.coro_get(node_hash),
                token=token)
        except KeyError:
            logger.debug("%s asked for a trie node we don't have: %s", peer, node_hash)
            continue
        nodes.append(node)
    peer.sub_proto.send_node_data(nodes)


def _test() -> None:
    import argparse
    import signal
    from p2p import ecies
    from p2p.kademlia import Node
    from p2p.peer import DEFAULT_PREFERRED_NODES
    from evm.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER, ROPSTEN_VM_CONFIGURATION
    from evm.db.backends.level import LevelDB
    from tests.p2p.integration_test_helpers import (
        FakeAsyncChainDB, FakeAsyncRopstenChain, FakeAsyncHeaderDB, connect_to_peers_loop)

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-fast', action="store_true")
    parser.add_argument('-light', action="store_true")
    parser.add_argument('-enode', type=str, required=False, help="The enode we should connect to")
    parser.add_argument('-debug', action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    loop = asyncio.get_event_loop()

    base_db = LevelDB(args.db)
    chaindb = FakeAsyncChainDB(base_db)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    headerdb = FakeAsyncHeaderDB(base_db)

    peer_class: Type[HeaderRequestingPeer] = ETHPeer
    if args.light:
        peer_class = LESPeer
    network_id = RopstenChain.network_id
    privkey = ecies.generate_privkey()
    peer_pool = PeerPool(peer_class, headerdb, network_id, privkey, ROPSTEN_VM_CONFIGURATION)
    if args.enode:
        nodes = tuple([Node.from_uri(args.enode)])
    else:
        nodes = DEFAULT_PREFERRED_NODES[network_id]

    asyncio.ensure_future(peer_pool.run())
    asyncio.ensure_future(connect_to_peers_loop(peer_pool, nodes))
    chain = FakeAsyncRopstenChain(base_db)
    syncer: BaseHeaderChainSyncer = None
    if args.fast:
        syncer = FastChainSyncer(chain, chaindb, peer_pool)
    elif args.light:
        syncer = LightChainSyncer(chain, headerdb, peer_pool)
    else:
        syncer = RegularChainSyncer(chain, chaindb, peer_pool)
    syncer.logger.setLevel(log_level)
    syncer.min_peers_to_sync = 1

    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint() -> None:
        await sigint_received.wait()
        await peer_pool.cancel()
        await syncer.cancel()
        loop.stop()

    async def run() -> None:
        await syncer.run()
        syncer.logger.info("run() finished, exiting")
        sigint_received.set()

    # loop.set_debug(True)
    asyncio.ensure_future(exit_on_sigint())
    asyncio.ensure_future(run())
    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    # Use the snippet below to get profile stats and print the top 50 functions by cumulative time
    # used.
    # import cProfile, pstats  # noqa
    # cProfile.run('_test()', 'stats')
    # pstats.Stats('stats').strip_dirs().sort_stats('cumulative').print_stats(50)
    _test()
