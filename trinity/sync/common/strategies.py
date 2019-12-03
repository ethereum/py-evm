from abc import (
    ABC,
    abstractmethod
)
import asyncio
import logging

from cancel_token import OperationCancelled
from eth_typing import (
    BlockNumber,
    Hash32,
)
from eth_utils import (
    humanize_seconds,
    ValidationError,
)

from eth.abc import (
    BlockHeaderAPI,
)
from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_PARENT_HASH,
)
from eth.exceptions import (
    HeaderNotFound,
)

from p2p.disconnect import DisconnectReason
from p2p.exceptions import (
    NoConnectedPeers,
    PeerConnectionLost,
)

from trinity.chains.base import AsyncChainAPI
from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity.protocol.common.peer import (
    BaseChainPeerPool,
)
from trinity.sync.beam.constants import (
    FULL_BLOCKS_NEEDED_TO_START_BEAM,
)
from trinity.sync.common.checkpoint import (
    Checkpoint,
)
from trinity.sync.common.constants import (
    MAX_SKELETON_REORG_DEPTH,
)


class SyncLaunchStrategyAPI(ABC):

    @abstractmethod
    async def fulfill_prerequisites(self) -> None:
        ...

    @abstractmethod
    def get_genesis_parent_hash(self) -> Hash32:
        ...

    @abstractmethod
    async def get_starting_block_number(self) -> BlockNumber:
        ...


class FromGenesisLaunchStrategy(SyncLaunchStrategyAPI):

    def __init__(self, db: BaseAsyncHeaderDB, chain: AsyncChainAPI) -> None:
        self._db = db
        self._chain = chain

    async def fulfill_prerequisites(self) -> None:
        pass

    def get_genesis_parent_hash(self) -> Hash32:
        return GENESIS_PARENT_HASH

    async def get_starting_block_number(self) -> BlockNumber:
        head = await self._db.coro_get_canonical_head()

        # When we start the sync with a peer, we always request up to MAX_REORG_DEPTH extra
        # headers before our current head's number, in case there were chain reorgs since the last
        # time _sync() was called. All of the extra headers that are already present in our DB
        # will be discarded so we don't unnecessarily process them again.
        return BlockNumber(max(GENESIS_BLOCK_NUMBER, head.block_number - MAX_SKELETON_REORG_DEPTH))


NON_RESPONSE_FROM_PEERS = (
    asyncio.TimeoutError,
    OperationCancelled,
    ValidationError,
)


class FromCheckpointLaunchStrategy(SyncLaunchStrategyAPI):

    # Wait at most 30 seconds before retrying, in case our estimate is wrong
    MAXIMUM_RETRY_SLEEP = 30

    min_block_number = BlockNumber(0)

    logger = logging.getLogger('trinity.sync.common.strategies.FromCheckpointLaunchStrategy')

    def __init__(self,
                 db: BaseAsyncHeaderDB,
                 chain: AsyncChainAPI,
                 checkpoint: Checkpoint,
                 peer_pool: BaseChainPeerPool) -> None:
        self._db = db
        self._chain = chain
        # We wrap the `FromGenesisLaunchStrategy` because we delegate to it at times and
        # reaching for inheritance seems wrong in this case.
        self._genesis_strategy = FromGenesisLaunchStrategy(self._db, self._chain)
        self._checkpoint = checkpoint
        self._peer_pool = peer_pool

    async def _are_prerequisites_complete(self, checkpoint: BlockHeaderAPI) -> bool:
        block_numbers_to_download = range(
            checkpoint.block_number + 1,  # we already have the checkpoint, we can skip it
            checkpoint.block_number + FULL_BLOCKS_NEEDED_TO_START_BEAM,
        )
        last_header = checkpoint
        for block_int in block_numbers_to_download:
            block_num = BlockNumber(block_int)
            try:
                next_header = await self._db.coro_get_canonical_block_header_by_number(block_num)
            except HeaderNotFound:
                self.logger.debug(
                    "Checkpoint validation header at #%d, parent %s, is missing. "
                    "Downloading from peers...",
                    block_num,
                    last_header,
                )
                return False
            else:
                if next_header.parent_hash != last_header.hash:
                    self.logger.warning(
                        "Checkpoint %s is not on the local canonical chain, which has "
                        "%s following %s. Forcing the checkpoint to be canonical...",
                        checkpoint,
                        next_header,
                        last_header,
                    )
                    # re-download from checkpoint to assert that the checkpoint is canonical
                    return False
                else:
                    self.logger.debug("Validated checkpoint %s locally", next_header)
                    last_header = next_header
        else:
            # if loop never breaks, then all headers are validated.
            return True

    async def fulfill_prerequisites(self) -> None:
        try:
            checkpoint = await self._db.coro_get_block_header_by_hash(self._checkpoint.block_hash)
        except HeaderNotFound:
            pass
        else:
            self.logger.debug("Found checkpoint header %s locally", checkpoint)
            self.min_block_number = checkpoint.block_number

            if await self._are_prerequisites_complete(checkpoint):
                self.logger.debug("Found all needed checkpoint headers locally, skipping download")
                return

        max_attempts = 1000

        for _attempt in range(max_attempts):
            try:
                peer = self._peer_pool.highest_td_peer
            except NoConnectedPeers:
                # Feels appropriate to wait a little longer while we aren't connected
                # to any peers yet.
                self.logger.debug("No peers are available to fulfill checkpoint prerequisites")
                await asyncio.sleep(2)
                continue

            try:
                headers = await peer.chain_api.get_block_headers(
                    self._checkpoint.block_hash,
                    max_headers=FULL_BLOCKS_NEEDED_TO_START_BEAM,
                    skip=0,
                    reverse=False,
                )
            except NON_RESPONSE_FROM_PEERS as exc:
                # Nothing to do here. The ExchangeManager will disconnect if appropriate
                # and eventually lead us to a better peer.
                self.logger.debug("%s did not return checkpoint prerequisites: %r", peer, exc)
                # Release the event loop so that "gone" peers don't keep getting returned here
                await asyncio.sleep(0)
                continue
            except PeerConnectionLost as exc:
                self.logger.debug("%s gone during checkpoint prerequisite request: %s", peer, exc)
                # Wait until peer is fully disconnected before continuing, so we don't reattempt
                # with the same peer repeatedly.
                await peer.disconnect(DisconnectReason.DISCONNECT_REQUESTED)
                continue

            if not headers:
                self.logger.debug(
                    "Disconnecting from %s. Returned no header while resolving checkpoint",
                    peer
                )
                await peer.disconnect(DisconnectReason.USELESS_PEER)
            else:
                header = headers[0]

                distance_shortage = FULL_BLOCKS_NEEDED_TO_START_BEAM - len(headers)
                if distance_shortage > 0:

                    if len(headers) == 1:
                        # We are exactly at the tip, spin another round so we can make a better ETA
                        self.logger.info(
                            "Checkpoint is too near the chain tip for Beam Sync to launch. "
                            "Beam Sync needs %d more headers to launch. Instead of waiting, "
                            "you can quit and restart with an older checkpoint.",
                            distance_shortage,
                        )
                        await asyncio.sleep(10)
                        continue

                    block_durations = tuple(
                        current.timestamp - previous.timestamp
                        for previous, current in zip(headers[:-1], headers[1:])
                    )

                    avg_blocktime = sum(block_durations) / len(block_durations)
                    wait_seconds = distance_shortage * avg_blocktime

                    self.logger.info(
                        "Checkpoint is too near the chain tip for Beam Sync to launch. "
                        "Beam Sync needs %d more headers to launch. Instead of waiting, "
                        "you can quit and restart with an older checkpoint."
                        "The wait time is roughly %s.",
                        distance_shortage,
                        humanize_seconds(wait_seconds),
                    )

                    await asyncio.sleep(min(wait_seconds, self.MAXIMUM_RETRY_SLEEP))
                    continue

                self.min_block_number = header.block_number
                await self._db.coro_persist_checkpoint_header(header, self._checkpoint.score)

                self.logger.debug(
                    "Successfully fulfilled checkpoint prereqs with %s: %s",
                    peer,
                    header,
                )
                return

            await asyncio.sleep(0.05)

        raise asyncio.TimeoutError(
            f"Failed to get checkpoint header within {max_attempts} attempts"
        )

    def get_genesis_parent_hash(self) -> Hash32:
        return self._checkpoint.block_hash

    async def get_starting_block_number(self) -> BlockNumber:
        block_number = await self._genesis_strategy.get_starting_block_number()
        return block_number if block_number > self.min_block_number else self.min_block_number
