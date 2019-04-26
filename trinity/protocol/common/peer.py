from abc import abstractmethod
import operator
import random
from typing import (
    Dict,
    List,
    NamedTuple,
    Tuple,
    Type,
)

from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth_utils.toolz import groupby

from eth.constants import GENESIS_BLOCK_NUMBER
from eth.vm.base import BaseVM

from p2p.exceptions import NoConnectedPeers
from p2p.kademlia import Node
from p2p.peer import (
    BasePeer,
    BasePeerFactory,
)
from p2p.peer_pool import (
    BasePeerPool,
)
from p2p.tracking.connection import (
    BaseConnectionTracker,
    NoopConnectionTracker,
)

from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity.protocol.common.handlers import BaseChainExchangeHandler

from trinity.plugins.builtin.network_db.connection.tracker import ConnectionTrackerClient

from .boot import DAOCheckBootManager
from .context import ChainContext


class ChainInfo(NamedTuple):
    block_number: BlockNumber
    block_hash: Hash32
    total_difficulty: int
    genesis_hash: Hash32

    network_id: int


class BaseChainPeer(BasePeer):
    boot_manager_class = DAOCheckBootManager
    context: ChainContext

    head_td: int = None
    head_hash: Hash32 = None
    head_number: BlockNumber = None
    network_id: int = None
    genesis_hash: Hash32 = None

    @property
    @abstractmethod
    def requests(self) -> BaseChainExchangeHandler:
        pass

    @property
    @abstractmethod
    def max_headers_fetch(self) -> int:
        pass

    @property
    def headerdb(self) -> BaseAsyncHeaderDB:
        return self.context.headerdb

    @property
    def local_network_id(self) -> int:
        return self.context.network_id

    @property
    def vm_configuration(self) -> Tuple[Tuple[int, Type[BaseVM]], ...]:
        return self.context.vm_configuration

    _local_genesis_hash: Hash32 = None

    async def _get_local_genesis_hash(self) -> Hash32:
        if self._local_genesis_hash is None:
            self._local_genesis_hash = await self.wait(
                self.headerdb.coro_get_canonical_block_hash(BlockNumber(GENESIS_BLOCK_NUMBER))
            )
        return self._local_genesis_hash

    @property
    async def _local_chain_info(self) -> ChainInfo:
        head = await self.wait(self.headerdb.coro_get_canonical_head())
        total_difficulty = await self.wait(self.headerdb.coro_get_score(head.hash))
        genesis_hash = await self._get_local_genesis_hash()
        return ChainInfo(
            block_number=head.block_number,
            block_hash=head.hash,
            total_difficulty=total_difficulty,
            genesis_hash=genesis_hash,
            network_id=self.local_network_id,
        )

    def setup_connection_tracker(self) -> BaseConnectionTracker:
        if self.has_event_bus:
            return ConnectionTrackerClient(self.get_event_bus())
        else:
            self.logger.warning(
                "No event_bus set on peer.  Connection tracking falling back to "
                "`NoopConnectionTracker`."
            )
            return NoopConnectionTracker()


class BaseChainPeerFactory(BasePeerFactory):
    context: ChainContext
    peer_class: Type[BaseChainPeer]


class BaseChainPeerPool(BasePeerPool):
    connected_nodes: Dict[Node, BaseChainPeer]  # type: ignore
    peer_factory_class: Type[BaseChainPeerFactory]

    @property
    def highest_td_peer(self) -> BaseChainPeer:
        peers = tuple(self.connected_nodes.values())
        if not peers:
            raise NoConnectedPeers()
        peers_by_td = groupby(operator.attrgetter('head_td'), peers)
        max_td = max(peers_by_td.keys())
        return random.choice(peers_by_td[max_td])

    def get_peers(self, min_td: int) -> List[BaseChainPeer]:
        # TODO: Consider turning this into a method that returns an AsyncIterator, to make it
        # harder for callsites to get a list of peers while making blocking calls, as those peers
        # might disconnect in the meantime.
        peers = tuple(self.connected_nodes.values())
        return [peer for peer in peers if peer.head_td >= min_td]

    def setup_connection_tracker(self) -> BaseConnectionTracker:
        if self.has_event_bus:
            return ConnectionTrackerClient(self.get_event_bus())
        else:
            return NoopConnectionTracker()
