from abc import (
    ABC,
    abstractmethod
)
import asyncio

from eth_typing import (
    BlockNumber,
    Hash32,
)
from eth_utils import (
    ValidationError,
)

from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_PARENT_HASH,
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
        return max(GENESIS_BLOCK_NUMBER, head.block_number - MAX_SKELETON_REORG_DEPTH)


class FromCheckpointLaunchStrategy(SyncLaunchStrategyAPI):

    min_block_number = BlockNumber(0)

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

    async def fulfill_prerequisites(self) -> None:
        max_attempts = 1000

        for _attempt in range(max_attempts):

            try:
                peer = self._peer_pool.highest_td_peer
            except NoConnectedPeers:
                # Feels appropriate to wait a little longer while we aren't connected
                # to any peers yet.
                await asyncio.sleep(2)
                continue

            try:
                headers = await peer.requests.get_block_headers(
                    self._checkpoint.block_hash,
                    max_headers=1,
                    skip=0,
                    reverse=False,
                )
            except (TimeoutError, PeerConnectionLost, ValidationError):
                # Nothing to do here. The ExchangeManager will disconnect if appropriate
                # and eventually lead us to a better peer.
                pass

            if not headers:
                await peer.disconnect(DisconnectReason.useless_peer)
            elif headers[0].hash != self._checkpoint.block_hash:
                await peer.disconnect(DisconnectReason.useless_peer)
            else:
                self.min_block_number = headers[0].block_number
                await self._db.coro_persist_checkpoint_header(headers[0], self._checkpoint.score)
                return

            await asyncio.sleep(0.05)

        raise TimeoutError(f"Failed to get checkpoint header within {max_attempts} attempts")

    def get_genesis_parent_hash(self) -> Hash32:
        return self._checkpoint.block_hash

    async def get_starting_block_number(self) -> BlockNumber:
        block_number = await self._genesis_strategy.get_starting_block_number()
        return block_number if block_number > self.min_block_number else self.min_block_number
