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

from trinity.db.header import BaseAsyncHeaderDB

from .boot import DAOCheckBootManager
from .context import ChainContext


class ChainInfo(NamedTuple):
    block_number: BlockNumber
    block_hash: Hash32
    total_difficulty: int
    genesis_hash: Hash32


TProtocol = TypeVar('TProtocol', bound=ChainProtocol)

class BaseChainPeer(BasePeer, Generic[TProtocol]):
    boot_manager_class = DAOCheckBootManager
    context: ChainContext

    head_td: int = None
    head_hash: Hash32 = None

    @property
    def chain_proto(self) -> TProtocol:
        if not isinstance(self.sub_proto, ChainProtocol):
            raise ValidationError(
                f"Expected to find a chain protocol on {self}, but got {self.sub_proto!r}"
            )
        else:
            return self.sub_proto


class BaseChainPeerFactory(BasePeerFactory):
    context: ChainContext


class BaseChainPeerPool(BasePeerPool):
    connected_nodes: Dict[Node, BaseChainPeer]  # type: ignore

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
