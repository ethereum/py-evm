import asyncio
from concurrent.futures import CancelledError
import math
import operator
from typing import (
    Any,
    Dict,
    List,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

from cancel_token import OperationCancelled
from cytoolz import (
    concat,
    merge,
    partition_all,
    unique,
)

from eth_typing import Hash32

from eth.constants import (
    BLANK_ROOT_HASH, EMPTY_UNCLE_HASH, GENESIS_PARENT_HASH)
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransaction

from p2p import protocol
from p2p.exceptions import NoEligiblePeers, PeerConnectionLost
from p2p.protocol import Command

from trinity.db.chain import AsyncChainDB
from trinity.protocol.eth import commands
from trinity.protocol.eth.constants import (
    MAX_BODIES_FETCH,
    MAX_RECEIPTS_FETCH,
    MAX_STATE_FETCH,
)
from trinity.protocol.eth.peer import ETHPeer
from trinity.protocol.eth.requests import HeaderRequest
from trinity.protocol.les.peer import LESPeer
from trinity.rlp.block_body import BlockBody
from trinity.sync.common.chain import BaseHeaderChainSyncer
from trinity.utils.timer import Timer

HeaderRequestingPeer = Union[LESPeer, ETHPeer]
# (ReceiptBundle, (Receipt, (root_hash, receipt_trie_data))
ReceiptBundle = Tuple[Tuple[Receipt, ...], Tuple[Hash32, Dict[Hash32, bytes]]]
# (BlockBody, (txn_root, txn_trie_data), uncles_hash)
BlockBodyBundle = Tuple[
    BlockBody,
    Tuple[Hash32, Dict[Hash32, bytes]],
    Hash32,
]


class FastChainSyncer(BaseHeaderChainSyncer):
    """
    Sync with the Ethereum network by fetching block headers/bodies and storing them in our DB.

    Here, the run() method returns as soon as we complete a sync with the peer that announced the
    highest TD, at which point we must run the StateDownloader to fetch the state for our chain
    head.
    """
    NO_PEER_RETRY_PAUSE = 5
    """If no peers are available for downloading the chain data, retry after this many seconds"""

    db: AsyncChainDB

    subscription_msg_types: Set[Type[Command]] = {
        commands.NewBlock,
        commands.GetBlockHeaders,
        commands.GetBlockBodies,
        commands.GetReceipts,
        commands.GetNodeData,
        # TODO: all of the following are here to quiet warning logging output
        # until the messages are properly handled.
        commands.Transactions,
        commands.NewBlockHashes,
    }

    async def _run(self) -> None:
        self.run_task(self._load_and_process_headers())
        await super()._run()

    async def _load_and_process_headers(self) -> None:
        while self.is_operational:
            # TODO invert this, so each peer is getting headers and completing them,
            # in independent loops
            # TODO implement the maximum task size at each step instead of this magic number
            max_headers = min((MAX_BODIES_FETCH, MAX_RECEIPTS_FETCH)) * 4
            batch_id, headers = await self.header_queue.get(max_headers)
            try:
                await self._process_headers(headers)
            except NoEligiblePeers:
                self.logger.info(
                    f"No available peers to sync with, retrying in {self.NO_PEER_RETRY_PAUSE}s"
                )
                self.header_queue.complete(batch_id, tuple())
                await self.sleep(self.NO_PEER_RETRY_PAUSE)
            else:
                self.header_queue.complete(batch_id, headers)

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

    async def _process_headers(self, headers: Tuple[BlockHeader, ...]) -> None:
        timer = Timer()
        target_td = await self._calculate_td(headers)
        bodies_by_key = await self._download_block_bodies(target_td, headers)
        self.logger.debug("Got block bodies for chain segment")

        await self._download_receipts(target_td, headers)
        self.logger.debug("Got block receipts for chain segment")

        for header in headers:
            if header.uncles_hash != EMPTY_UNCLE_HASH:
                key = (header.transaction_root, header.uncles_hash)
                body = cast(BlockBody, bodies_by_key[key])
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
        txs = sum(len(cast(BlockBody, body).transactions) for body in bodies_by_key.values())
        self.logger.info(
            "Imported %d blocks (%d txs) in %0.2f seconds, new head: #%d",
            len(headers), txs, timer.elapsed, head.block_number)

        # during fast sync, exit the service when reaching the target hash
        target_hash = self.get_target_header_hash()

        # Quite often the header batch we receive includes headers past the peer's reported
        # head (via the NewBlock msg), so we can't compare our head's hash to the peer's in
        # order to see if the sync is completed. Instead we just check that we have the peer's
        # head_hash in our chain.
        if await self.wait(self.db.coro_header_exists(target_hash)):
            self.cancel_nowait()

    async def _download_block_bodies(self,
                                     target_td: int,
                                     all_headers: Tuple[BlockHeader, ...]
                                     ) -> Dict[Tuple[Hash32, Hash32], BlockBody]:
        """
        Downloads and persists the block bodies for the given set of block headers.
        Block bodies are requested from all peers in equal sized batches.
        """
        headers = tuple(header for header in all_headers if not _is_body_empty(header))
        block_bodies_by_key: Dict[Tuple[Hash32, Hash32], BlockBody] = {}

        while headers:
            # split the remaining headers into equal sized batches for each peer.
            peers = cast(Tuple[ETHPeer, ...], self.peer_pool.get_peers(target_td))
            if not peers:
                raise NoEligiblePeers(
                    "No connected peers have the block bodies we need for td={0}".format(target_td)
                )
            batch_size = math.ceil(len(headers) / len(peers))
            batches = tuple(partition_all(batch_size, headers))

            # issue requests to all of the peers and wait for all of them to respond.
            requests = tuple(
                self._get_block_bodies(peer, batch)
                for peer, batch
                in zip(peers, batches)
            )
            responses = await self.wait(asyncio.gather(
                *requests,
                loop=self.get_event_loop(),
            ))

            # extract the returned block body data and the headers for which we
            # are still missing block bodies.
            all_block_body_bundles, all_missing_headers = zip(*responses)

            for (body, (tx_root, trie_data_dict), uncles_hash) in concat(all_block_body_bundles):
                await self.wait(self.db.coro_persist_trie_data_dict(trie_data_dict))

            block_bodies_by_key = merge(block_bodies_by_key, {
                (transaction_root, uncles_hash): block_body
                for block_body, (transaction_root, trie_dict_data), uncles_hash
                in concat(all_block_body_bundles)
            })
            headers = tuple(concat(all_missing_headers))

        self.logger.debug("Got block bodies batch for %d headers", len(all_headers))
        return block_bodies_by_key

    async def _get_block_bodies(self,
                                peer: ETHPeer,
                                batch: Tuple[BlockHeader, ...],
                                ) -> Tuple[Tuple[BlockBodyBundle, ...], Tuple[BlockHeader, ...]]:
        """
        Requests the batch of block bodies from the given peer, returning the
        returned block bodies data and the headers for which block bodies were not
        returned.
        """
        self.logger.debug("Requesting block bodies for %d headers from %s", len(batch), peer)
        try:
            block_body_bundles = await peer.requests.get_block_bodies(batch)
        except TimeoutError as err:
            self.logger.debug(
                "Timed out requesting block bodies for %d headers from %s", len(batch), peer,
            )
            return tuple(), batch
        except CancelledError:
            self.logger.debug("Pending block bodies call to %r future cancelled", peer)
            return tuple(), batch
        except OperationCancelled:
            self.logger.trace("Pending block bodies call to %r operation cancelled", peer)
            return tuple(), batch
        except PeerConnectionLost:
            self.logger.debug("Peer went away, cancelling the block body request and moving on...")
            return tuple(), batch
        except Exception:
            self.logger.exception("Unknown error when getting block bodies")
            return tuple(), batch
        else:
            self.logger.debug(
                "Got block bodies for %d headers from %s", len(block_body_bundles), peer,
            )

        if not block_body_bundles:
            return tuple(), batch

        _, trie_roots_and_data_dicts, uncles_hashes = zip(*block_body_bundles)

        received_keys = {
            (root_hash, uncles_hash)
            for (root_hash, _), uncles_hash
            in zip(trie_roots_and_data_dicts, uncles_hashes)
        }

        missing = tuple(
            header
            for header
            in batch
            if (header.transaction_root, header.uncles_hash) not in received_keys
        )

        return block_body_bundles, missing

    async def _download_receipts(self,
                                 target_td: int,
                                 all_headers: Tuple[BlockHeader, ...]) -> None:
        """
        Downloads and persists the receipts for the given set of block headers.
        Receipts are requested from all peers in equal sized batches.
        """
        # Post-Byzantium blocks may have identical receipt roots (e.g. when they have the same
        # number of transactions and all succeed/failed: ropsten blocks 2503212 and 2503284),
        # so we do this to avoid requesting the same receipts multiple times.
        headers = tuple(unique(
            (header for header in all_headers if not _is_receipts_empty(header)),
            key=operator.attrgetter('receipt_root'),
        ))

        while headers:
            # split the remaining headers into equal sized batches for each peer.
            peers = cast(Tuple[ETHPeer, ...], self.peer_pool.get_peers(target_td))
            if not peers:
                raise NoEligiblePeers(
                    "No connected peers have the receipts we need for td={0}".format(target_td)
                )
            batch_size = math.ceil(len(headers) / len(peers))
            batches = tuple(partition_all(batch_size, headers))

            # issue requests to all of the peers and wait for all of them to respond.
            requests = tuple(
                self._get_receipts(peer, batch)
                for peer, batch
                in zip(peers, batches)
            )
            responses = await self.wait(asyncio.gather(
                *requests,
                loop=self.get_event_loop(),
            ))

            # extract the returned receipt data and the headers for which we
            # are still missing receipts.
            all_receipt_bundles, all_missing_headers = zip(*responses)
            receipt_bundles = tuple(concat(all_receipt_bundles))
            headers = tuple(concat(all_missing_headers))

            if len(receipt_bundles) == 0:
                continue

            # process all of the returned receipts, storing their trie data
            # dicts in the database
            receipts, trie_roots_and_data_dicts = zip(*receipt_bundles)
            trie_roots, trie_data_dicts = zip(*trie_roots_and_data_dicts)
            for trie_data in trie_data_dicts:
                await self.wait(self.db.coro_persist_trie_data_dict(trie_data))

        self.logger.debug("Got receipts batch for %d headers", len(all_headers))

    async def _get_receipts(self,
                            peer: ETHPeer,
                            batch: Tuple[BlockHeader, ...],
                            ) -> Tuple[Tuple[ReceiptBundle, ...], Tuple[BlockHeader, ...]]:
        """
        Requests the batch of receipts from the given peer, returning the
        returned receipt data and the headers for which receipts were not
        returned for.
        """
        self.logger.debug("Requesting receipts for %d headers from %s", len(batch), peer)
        try:
            receipt_bundles = await peer.requests.get_receipts(batch)
        except TimeoutError as err:
            self.logger.debug(
                "Timed out requesting receipts for %d headers from %s", len(batch), peer,
            )
            return tuple(), batch
        except CancelledError:
            self.logger.debug("Pending receipts call to %r future cancelled", peer)
            return tuple(), batch
        except OperationCancelled:
            self.logger.trace("Pending receipts call to %r operation cancelled", peer)
            return tuple(), batch
        except PeerConnectionLost:
            self.logger.debug("Peer went away, cancelling the receipts request and moving on...")
            return tuple(), batch
        except Exception:
            self.logger.exception("Unknown error when getting receipts")
            return tuple(), batch
        else:
            self.logger.debug(
                "Got receipts for %d headers from %s", len(receipt_bundles), peer,
            )

        if not receipt_bundles:
            return tuple(), batch

        receipts, trie_roots_and_data_dicts = zip(*receipt_bundles)
        receipt_roots, trie_data_dicts = zip(*trie_roots_and_data_dicts)
        receipt_roots_set = set(receipt_roots)
        missing = tuple(
            header
            for header
            in batch
            if header.receipt_root not in receipt_roots_set
        )

        return receipt_bundles, missing

    async def _handle_msg(self, peer: HeaderRequestingPeer, cmd: protocol.Command,
                          msg: protocol._DecodedMsgType) -> None:
        peer = cast(ETHPeer, peer)

        # TODO: stop ignoring these once we have proper handling for these messages.
        ignored_commands = (commands.Transactions, commands.NewBlockHashes)

        if isinstance(cmd, ignored_commands):
            pass
        elif isinstance(cmd, commands.NewBlock):
            await self._handle_new_block(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, commands.GetBlockHeaders):
            await self._handle_get_block_headers(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, commands.GetBlockBodies):
            # Only serve up to MAX_BODIES_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:MAX_BODIES_FETCH]
            await self._handler.handle_get_block_bodies(peer, block_hashes)
        elif isinstance(cmd, commands.GetReceipts):
            # Only serve up to MAX_RECEIPTS_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:MAX_RECEIPTS_FETCH]
            await self._handler.handle_get_receipts(peer, block_hashes)
        elif isinstance(cmd, commands.GetNodeData):
            # Only serve up to MAX_STATE_FETCH items in every request.
            node_hashes = cast(List[Hash32], msg)[:MAX_STATE_FETCH]
            await self._handler.handle_get_node_data(peer, node_hashes)
        else:
            self.logger.debug("%s msg not handled yet, need to be implemented", cmd)

    async def _handle_new_block(self, peer: ETHPeer, msg: Dict[str, Any]) -> None:
        self._sync_requests.put_nowait(peer)

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
    _seal_check_random_sample_rate = 1

    async def _process_headers(self, headers: Tuple[BlockHeader, ...]) -> None:
        target_td = await self._calculate_td(headers)
        bodies_by_key = await self._download_block_bodies(target_td, headers)
        self.logger.info("Got block bodies for chain segment")

        for header in headers:
            vm_class = self.chain.get_vm_class_for_block_number(header.block_number)
            block_class = vm_class.get_block_class()

            if _is_body_empty(header):
                transactions: List[BaseTransaction] = []
                uncles: List[BlockHeader] = []
            else:
                key = (header.transaction_root, header.uncles_hash)
                body = cast(BlockBody, bodies_by_key[key])
                tx_class = block_class.get_transaction_class()
                transactions = [tx_class.from_base_transaction(tx)
                                for tx in body.transactions]
                uncles = body.uncles

            block = block_class(header, transactions, uncles)
            timer = Timer()
            _, new_canonical_blocks, old_canonical_blocks = await self.wait(
                self.chain.coro_import_block(block, perform_validation=True)
            )

            if new_canonical_blocks == (block,):
                # simple import of a single new block.
                self.logger.info("Imported block %d (%d txs) in %f seconds",
                                 block.number, len(transactions), timer.elapsed)
            elif not new_canonical_blocks:
                # imported block from a fork.
                self.logger.info("Imported non-canonical block %d (%d txs) in %f seconds",
                                 block.number, len(transactions), timer.elapsed)
            elif old_canonical_blocks:
                self.logger.info(
                    "Chain Reorganization: Imported block %d (%d txs) in %f "
                    "seconds, %d blocks discarded and %d new canonical blocks added",
                    block.number,
                    len(transactions),
                    timer.elapsed,
                    len(old_canonical_blocks),
                    len(new_canonical_blocks),
                )
            else:
                raise Exception("Invariant: unreachable code path")

        head = await self.wait(self.db.coro_get_canonical_head())
        self.logger.info("Imported chain segment, new head: #%d", head.block_number)


def _is_body_empty(header: BlockHeader) -> bool:
    return header.transaction_root == BLANK_ROOT_HASH and header.uncles_hash == EMPTY_UNCLE_HASH


def _is_receipts_empty(header: BlockHeader) -> bool:
    return header.receipt_root == BLANK_ROOT_HASH
