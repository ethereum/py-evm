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
from eth.rlp.headers import BlockHeader
from eth.vm.base import BaseVM

from p2p.exceptions import NoConnectedPeers
from p2p.kademlia import Node
from p2p.peer import (
    BasePeer,
    BasePeerFactory,
    BasePeerPool,
)

from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity.protocol.common.handlers import BaseChainExchangeHandler

from .boot import DAOCheckBootManager
from .context import ChainContext


class ChainInfo(NamedTuple):
    block_number: BlockNumber
    block_hash: Hash32
    total_difficulty: int
    genesis_hash: Hash32


class BaseChainPeer(BasePeer):
    boot_manager_class = DAOCheckBootManager
    context: ChainContext

    head_td: int = None
    head_hash: Hash32 = None
    head_number: BlockNumber = None

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
    def network_id(self) -> int:
        return self.context.network_id

    @property
    def vm_configuration(self) -> Tuple[Tuple[int, Type[BaseVM]], ...]:
        return self.context.vm_configuration

    @property
    async def genesis(self) -> BlockHeader:
        genesis_hash = await self.wait(
            self.headerdb.coro_get_canonical_block_hash(BlockNumber(GENESIS_BLOCK_NUMBER)))
        return await self.wait(self.headerdb.coro_get_block_header_by_hash(genesis_hash))

    @property
    async def _local_chain_info(self) -> ChainInfo:
        genesis = await self.genesis
        head = await self.wait(self.headerdb.coro_get_canonical_head())
        total_difficulty = await self.headerdb.coro_get_score(head.hash)
        return ChainInfo(
            block_number=head.block_number,
            block_hash=head.hash,
            total_difficulty=total_difficulty,
            genesis_hash=genesis.hash,
        )


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
