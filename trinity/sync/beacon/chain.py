import asyncio
import itertools
from typing import (
    Tuple,
    AsyncGenerator,
)

from eth_utils import (
    ValidationError,
)

from cancel_token import (
    CancelToken,
)

from p2p.service import (
    BaseService,
)

from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)
from eth2.beacon.db.exceptions import FinalizedHeadNotFound
from eth2.beacon.typing import (
    Slot,
)

from trinity.db.beacon.chain import BaseAsyncBeaconChainDB
from trinity.protocol.bcc_libp2p.node import PeerPool, Peer
from trinity.sync.beacon.constants import (
    MAX_BLOCKS_PER_REQUEST,
    PEER_SELECTION_RETRY_INTERVAL,
    PEER_SELECTION_MAX_RETRIES,
)
from trinity.sync.common.chain import (
    SyncBlockImporter,
)
from eth2.configs import (
    Eth2GenesisConfig,
)
from trinity.protocol.bcc_libp2p.exceptions import RequestFailure


class BeaconChainSyncer(BaseService):
    """Sync from our finalized head until their preliminary head."""

    chain_db: BaseAsyncBeaconChainDB
    peer_pool: PeerPool
    block_importer: SyncBlockImporter
    genesis_config: Eth2GenesisConfig
    sync_peer: Peer

    def __init__(self,
                 chain_db: BaseAsyncBeaconChainDB,
                 peer_pool: PeerPool,
                 block_importer: SyncBlockImporter,
                 genesis_config: Eth2GenesisConfig,
                 token: CancelToken = None) -> None:
        super().__init__(token)

        self.chain_db = chain_db
        self.peer_pool = peer_pool
        self.block_importer = block_importer
        self.genesis_config = genesis_config

        self.sync_peer = None

    @property
    def is_sync_peer_selected(self) -> bool:
        return self.sync_peer is not None

    async def _run(self) -> None:
        for retry in itertools.count():
            is_last_retry = retry == PEER_SELECTION_MAX_RETRIES - 1
            if retry >= PEER_SELECTION_MAX_RETRIES:
                raise Exception("Invariant: Cannot exceed max retries")

            try:
                self.sync_peer = await self.wait(self.select_sync_peer())
            except ValidationError as exception:
                self.logger.info(f"No suitable peers to sync with: {exception}")
                if is_last_retry:
                    # selecting sync peer has failed
                    break
                else:
                    # wait some time and try again
                    await asyncio.sleep(PEER_SELECTION_RETRY_INTERVAL)
                    continue
            else:
                # sync peer selected successfully
                break

            raise Exception("Unreachable")

        if not self.is_sync_peer_selected:
            self.logger.info("Failed to find suitable sync peer in time")
            return

        await self.wait(self.sync())

        new_head = await self.chain_db.coro_get_canonical_head(BeaconBlock)
        self.logger.info(f"Sync with {self.sync_peer} finished, new head: {new_head}")

    async def select_sync_peer(self) -> Peer:
        if len(self.peer_pool) == 0:
            raise ValidationError("Not connected to anyone")

        best_peer = self.peer_pool.get_best_head_slot_peer()

        try:
            finalized_head = await self.chain_db.coro_get_finalized_head(BeaconBlock)
        # TODO(ralexstokes) look at better way to handle once we have fork choice in place
        except FinalizedHeadNotFound:
            return best_peer

        if best_peer.head_slot <= finalized_head.slot:
            raise ValidationError("No peer that is ahead of us")

        return best_peer

    async def sync(self) -> None:

        try:
            finalized_head = await self.chain_db.coro_get_finalized_head(BeaconBlock)
            finalized_slot = finalized_head.slot
        # TODO(ralexstokes) look at better way to handle once we have fork choice in place
        except FinalizedHeadNotFound:
            finalized_slot = self.genesis_config.GENESIS_SLOT

        self.logger.info(
            "Syncing with %s (their head slot: %d, our finalized slot: %d)",
            self.sync_peer,
            self.sync_peer.head_slot,
            finalized_slot,
        )
        start_slot = finalized_slot + 1
        batches = self.request_batches(start_slot)

        last_block = None
        async for batch in batches:
            if last_block is None:
                try:
                    await self.validate_first_batch(batch)
                except ValidationError as error:
                    self.logger.debug("Invalid first batch: %s", error)
                    return
            else:
                if batch[0].parent_root != last_block.signing_root:
                    self.logger.info(f"Received batch is not linked to previous one")
                    break
            last_block = batch[-1]

            for block in batch:
                # Copied from `RegularChainBodySyncer._import_blocks`
                try:
                    _, new_canonical_blocks, old_canonical_blocks = self.block_importer.import_block(block)  # noqa: E501

                    if new_canonical_blocks == (block,):
                        # simple import of a single new block.
                        self.logger.info("Imported block %d", block.slot)
                    elif not new_canonical_blocks:
                        # imported block from a fork.
                        self.logger.info("Imported non-canonical block %d", block.slot)
                    elif old_canonical_blocks:
                        self.logger.info(
                            "Chain Reorganization: Imported block %d"
                            ", %d blocks discarded and %d new canonical blocks added",
                            block.slot,
                            len(old_canonical_blocks),
                            len(new_canonical_blocks),
                        )
                    else:
                        raise Exception("Invariant: unreachable code path")
                except ValidationError as error:
                    self.logger.info(f"Received invalid block from {self.sync_peer}: {error}")
                    break

    async def request_batches(self,
                              start_slot: Slot,
                              ) -> AsyncGenerator[Tuple[BaseBeaconBlock, ...], None]:
        slot = start_slot
        while True:
            self.logger.debug(
                "Requesting blocks from %s starting at #%d", self.sync_peer, slot
            )
            try:
                batch = await self.sync_peer.request_beacon_blocks_by_range(
                    slot, MAX_BLOCKS_PER_REQUEST
                )
            except RequestFailure as error:
                self.logger.debug("Request batch failed  reason: %s", error)
                break

            if len(batch) == 0:
                break

            yield batch

            slot = batch[-1].slot + 1
            if slot > self.sync_peer.head_slot:
                break

    async def validate_first_batch(self, batch: Tuple[BaseBeaconBlock, ...]) -> None:
        try:
            first_block = batch[0]
        except IndexError:
            raise ValidationError("Batch is empty")

        if first_block.slot == 0:
            raise ValidationError(
                "Invariant: Syncing starts with the child of a finalized block, so never with the "
                "genesis block"
            )

        parent = await self.chain_db.coro_get_block_by_root(
            first_block.parent_root,
            BeaconBlock,
        )
        finalized_head = await self.chain_db.coro_get_finalized_head(BeaconBlock)

        if parent.signing_root != finalized_head.signing_root:
            message = f"Peer has different block finalized at slot #{parent.slot}"
            self.logger.info(message)
            self.logger.info(
                "first_batch_parent %s, finalized_head %s",
                parent,
                finalized_head,
            )
            raise ValidationError(message)
