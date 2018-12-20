import operator
from typing import (
    cast,
    Tuple,
    Iterable,
    AsyncGenerator,
)

from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import (
    first,
)

from cancel_token import (
    CancelToken,
)

from p2p.service import (
    BaseService,
)

from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.db.chain import BaseBeaconChainDB

from trinity.protocol.bcc.peer import (
    BCCPeer,
    BCCPeerPool,
)
from trinity.sync.beacon.constants import (
    MAX_BLOCKS_PER_REQUEST,
)


class BeaconChainSyncer(BaseService):
    """Sync from our finalized head until their preliminary head."""

    def __init__(self,
                 chain_db: BaseBeaconChainDB,
                 peer_pool: BCCPeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)

        self.chain_db = chain_db
        self.peer_pool = peer_pool

        self.sync_peer: BCCPeer = None

    async def _run(self) -> None:
        self.sync_peer = self.select_sync_peer()
        if not self.sync_peer:
            self.logger.info("No suitable peers to sync with")

        await self.sync()

        new_head = self.chain_db.get_canonical_head()
        self.logger.info(f"Sync with {self.sync_peer} finished, new head: {new_head}")

    def select_sync_peer(self) -> BCCPeer:
        if len(self.peer_pool) == 0:
            return None

        # choose the peer with the highest head slot
        peers = cast(Iterable[BCCPeer], self.peer_pool.connected_nodes.values())
        sorted_peers = sorted(peers, key=operator.attrgetter("head_slot"), reverse=True)
        best_peer = first(sorted_peers)

        finalized_head_slot = self.chain_db.get_finalized_head().slot
        if best_peer.head_slot <= finalized_head_slot:
            return None

        return best_peer

    async def sync(self) -> None:
        self.logger.info(
            "Syncing with %s (their head slot: %d, our finalized slot: %d)",
            self.sync_peer,
            self.sync_peer.head_slot,
            self.chain_db.get_finalized_head().slot,
        )

        start_slot = self.chain_db.get_finalized_head().slot + 1
        batches = self.request_batches(start_slot)

        last_block = None
        async for batch in batches:
            if last_block is None:
                try:
                    self.validate_first_batch(batch)
                except ValidationError:
                    return
            else:
                if batch[0].parent_root != last_block.hash:
                    self.logger.info(f"Received batch is not linked to previous one")
                    break
            last_block = batch[-1]

            try:
                self.chain_db.persist_block_chain(batch)
            except ValidationError as exception:
                self.logger.info(f"Received invalid batch from {self.sync_peer}: {exception}")
                break

    async def request_batches(self,
                              start_slot: int
                              ) -> AsyncGenerator[Tuple[BaseBeaconBlock, ...], None]:
        slot = start_slot
        while True:
            self.logger.debug(
                "Requesting blocks from %s starting at #%d",
                self.sync_peer,
                slot,
            )

            batch = await self.sync_peer.requests.get_beacon_blocks(
                slot,
                MAX_BLOCKS_PER_REQUEST,
            )

            if len(batch) == 0:
                break

            yield batch

            slot = batch[-1].slot + 1

    def validate_first_batch(self, batch: Tuple[BaseBeaconBlock, ...]) -> None:
        parent_root = batch[0].parent_root
        parent_slot = batch[0].slot - 1

        if parent_slot < 0:
            raise Exception(
                "Invariant: Syncing starts with the child of a finalized block, so never with the "
                "genesis block"
            )

        canonical_cousin = self.chain_db.get_canonical_block_by_slot(parent_slot)
        if canonical_cousin.hash != parent_root:
            self.logger.info(f"Peer has different block finalized at slot #{parent_root}")
            raise ValidationError()
