from typing import (
    AsyncIterator,
    Tuple,
)

from cancel_token import (
    CancelToken,
    OperationCancelled,
)

from eth.constants import GENESIS_BLOCK_NUMBER
from eth.exceptions import (
    HeaderNotFound,
)
from eth_typing import (
    BlockNumber,
    Hash32,
)
from eth_utils import (
    encode_hex,
    ValidationError,
)
from eth.rlp.headers import (
    BlockHeader,
)

from p2p.constants import (
    MAX_REORG_DEPTH,
    SEAL_CHECK_RANDOM_SAMPLE_RATE,
)
from p2p.p2p_proto import (
    DisconnectReason,
)
from p2p.service import (
    BaseService,
)

from trinity.chains.base import BaseAsyncChain
from trinity.db.header import AsyncHeaderDB
from trinity.protocol.common.peer import (
    BaseChainPeer,
)

from .types import SyncProgress


class PeerHeaderSyncer(BaseService):
    """
    Sync as many headers as possible with a given peer.

    Here, the run() method will execute the sync loop until our local head is the same as the one
    with the highest TD announced by any of our peers.
    """
    _seal_check_random_sample_rate = SEAL_CHECK_RANDOM_SAMPLE_RATE

    def __init__(self,
                 chain: BaseAsyncChain,
                 db: AsyncHeaderDB,
                 peer: BaseChainPeer,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.db = db
        self.sync_progress: SyncProgress = None
        self._peer = peer
        self._target_header_hash = peer.head_hash

    def get_target_header_hash(self) -> Hash32:
        if self._target_header_hash is None:
            raise ValidationError("Cannot check the target hash when there is no active sync")
        else:
            return self._target_header_hash

    async def _run(self) -> None:
        await self.events.cancelled.wait()

    async def next_header_batch(self) -> AsyncIterator[Tuple[BlockHeader, ...]]:
        """Try to fetch headers until the given peer's head_hash.

        Returns when the peer's head_hash is available in our ChainDB, or if any error occurs
        during the sync.
        """
        peer = self._peer

        head = await self.wait(self.db.coro_get_canonical_head())
        head_td = await self.wait(self.db.coro_get_score(head.hash))
        if peer.head_td <= head_td:
            self.logger.info(
                "Head TD (%d) announced by %s not higher than ours (%d), not syncing",
                peer.head_td, peer, head_td)
            return
        else:
            self.logger.debug(
                "%s announced Head TD %d, which is higher than ours (%d), starting sync",
                peer, peer.head_td, head_td)
        self.sync_progress = SyncProgress(head.block_number, head.block_number, peer.head_number)
        self.logger.info("Starting sync with %s", peer)
        last_received_header: BlockHeader = None
        # When we start the sync with a peer, we always request up to MAX_REORG_DEPTH extra
        # headers before our current head's number, in case there were chain reorgs since the last
        # time _sync() was called. All of the extra headers that are already present in our DB
        # will be discarded by _fetch_missing_headers() so we don't unnecessarily process them
        # again.
        start_at = max(GENESIS_BLOCK_NUMBER + 1, head.block_number - MAX_REORG_DEPTH)
        while self.is_operational:
            if not peer.is_operational:
                self.logger.info("%s disconnected, aborting sync", peer)
                break

            try:
                all_headers = await self.wait(self._request_headers(peer, start_at))
                if last_received_header is None:
                    # Skip over existing headers on the first run-through
                    headers = tuple(
                        # The inner list comprehension is needed because async_generators
                        # cannot be cast to a tuple.
                        [header async for header in self._get_missing_tail(all_headers)]
                    )
                    if len(headers) == 0 and len(all_headers) > 0:
                        head = await self.wait(self.db.coro_get_canonical_head())
                        start_at = max(
                            all_headers[-1].block_number + 1,
                            head.block_number - MAX_REORG_DEPTH
                        )
                        self.logger.debug(
                            "All %d headers redundant, head at %s, fetching from #%d",
                            len(all_headers),
                            head,
                            start_at,
                        )
                        continue
                else:
                    headers = all_headers
                self.logger.debug2('sync received new headers', headers)
            except OperationCancelled:
                self.logger.info("Sync with %s completed", peer)
                break
            except TimeoutError:
                self.logger.warning("Timeout waiting for header batch from %s, aborting sync", peer)
                await peer.disconnect(DisconnectReason.timeout)
                break
            except ValidationError as err:
                self.logger.warning(
                    "Invalid header response sent by peer %s disconnecting: %s",
                    peer, err,
                )
                await peer.disconnect(DisconnectReason.useless_peer)
                break

            if not headers:
                if last_received_header is None:
                    request_parent = head
                else:
                    request_parent = last_received_header
                if head_td < peer.head_td:
                    # peer claims to have a better header, but didn't return it. Boot peer
                    # TODO ... also blacklist, because it keeps trying to reconnect
                    self.logger.warning(
                        "%s announced difficulty %s, but didn't return any headers after %r@%s",
                        peer,
                        peer.head_td,
                        request_parent,
                        head_td,
                    )
                    await peer.disconnect(DisconnectReason.subprotocol_error)
                else:
                    self.logger.info("Got no new headers from %s, aborting sync", peer)
                break

            first = headers[0]
            first_parent = None
            if last_received_header is None:
                # on the first request, make sure that the earliest ancestor has a parent in our db
                try:
                    first_parent = await self.wait(
                        self.db.coro_get_block_header_by_hash(first.parent_hash)
                    )
                except HeaderNotFound:
                    self.logger.warning(
                        "Unable to find common ancestor betwen our chain and %s",
                        peer,
                    )
                    break
            elif last_received_header.hash != first.parent_hash:
                # on follow-ups, require the first header in this batch to be next in succession
                self.logger.warning(
                    "Header batch starts with %r, with parent %s, but last header was %r",
                    first,
                    encode_hex(first.parent_hash[:4]),
                    last_received_header,
                )
                break

            self.logger.debug(
                "Got new header chain from %s: %s..%s",
                peer,
                first,
                headers[-1],
            )
            try:
                await self.chain.coro_validate_chain(
                    last_received_header or first_parent,
                    headers,
                    self._seal_check_random_sample_rate,
                )
            except ValidationError as e:
                self.logger.warning("Received invalid headers from %s, disconnecting: %s", peer, e)
                await peer.disconnect(DisconnectReason.subprotocol_error)
                break

            for header in headers:
                head_td += header.difficulty

            # Setting the latest header hash for the peer, before queuing header processing tasks
            self._target_header_hash = peer.head_hash

            yield headers
            last_received_header = headers[-1]
            self.sync_progress = self.sync_progress.update_current_block(
                last_received_header.block_number,
            )
            start_at = last_received_header.block_number + 1

    async def _request_headers(
            self, peer: BaseChainPeer, start_at: BlockNumber) -> Tuple[BlockHeader, ...]:
        """Fetch a batch of headers starting at start_at and return the ones we're missing."""
        self.logger.debug("Requsting chain of headers from %s starting at #%d", peer, start_at)

        return await peer.requests.get_block_headers(
            start_at,
            peer.max_headers_fetch,
            skip=0,
            reverse=False,
        )

    async def _get_missing_tail(
            self,
            headers: Tuple[BlockHeader, ...]) -> AsyncIterator[BlockHeader]:
        """
        We only want headers that are missing, so we iterate over the list
        until we find the first missing header, after which we return all of
        the remaining headers.
        """
        iter_headers = iter(headers)
        for header in iter_headers:
            is_present = await self.wait(self.db.coro_header_exists(header.hash))
            if is_present:
                self.logger.debug("Discarding header that we already have: %s", header)
            else:
                yield header
                break

        for header in iter_headers:
            yield header
