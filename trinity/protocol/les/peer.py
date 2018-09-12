import operator
import random
from typing import (
    Any,
    cast,
    Dict,
    List,
    Union,
    Tuple,
    Type,
)

from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth_utils import encode_hex
from eth_utils.toolz import groupby

from eth.constants import GENESIS_BLOCK_NUMBER
from eth.rlp.headers import BlockHeader
from eth.vm.base import BaseVM

from p2p.exceptions import (
    HandshakeFailure,
    NoConnectedPeers,
)
from p2p.kademlia import Node
from p2p.p2p_proto import DisconnectReason
from p2p.peer import (
    BasePeer,
    BasePeerPool,
    BasePeerFactory,
)
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)

from trinity.db.header import BaseAsyncHeaderDB
from trinity.protocol.common.boot import (
    DAOCheckBootManager,
)
from trinity.protocol.common.context import (
    ChainContext,
)
from trinity.protocol.common.proto import (
    ChainInfo,
)

from .commands import (
    Announce,
    Status,
    StatusV2,
)
from .constants import (
    MAX_HEADERS_FETCH,
)
from .proto import (
    LESProtocol,
    LESProtocolV2,
)
from .handlers import LESExchangeHandler


class LESPeer(BasePeer):
    head_td: int = None
    head_hash: Hash32 = None

    context: ChainContext

    max_headers_fetch = MAX_HEADERS_FETCH

    _supported_sub_protocols = [LESProtocol, LESProtocolV2]
    sub_proto: LESProtocol = None

    _requests: LESExchangeHandler = None
    head_number: BlockNumber = None

    boot_manager_class = DAOCheckBootManager

    def get_extra_stats(self) -> List[str]:
        stats_pairs = self.requests.get_stats().items()
        return ['%s: %s' % (cmd_name, stats) for cmd_name, stats in stats_pairs]

    @property
    def requests(self) -> LESExchangeHandler:
        if self._requests is None:
            self._requests = LESExchangeHandler(self)
        return self._requests

    def handle_sub_proto_msg(self, cmd: Command, msg: _DecodedMsgType) -> None:
        head_info = cast(Dict[str, Union[int, Hash32, BlockNumber]], msg)
        if isinstance(cmd, Announce):
            self.head_td = head_info['head_td']
            self.head_hash = head_info['head_hash']
            self.head_number = head_info['head_number']

        super().handle_sub_proto_msg(cmd, msg)

    async def send_sub_proto_handshake(self) -> None:
        self.sub_proto.send_handshake(await self._local_chain_info)

    async def process_sub_proto_handshake(
            self, cmd: Command, msg: _DecodedMsgType) -> None:
        if not isinstance(cmd, (Status, StatusV2)):
            await self.disconnect(DisconnectReason.subprotocol_error)
            raise HandshakeFailure(
                "Expected a LES Status msg, got {}, disconnecting".format(cmd))
        msg = cast(Dict[str, Any], msg)
        if msg['networkId'] != self.network_id:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                "{} network ({}) does not match ours ({}), disconnecting".format(
                    self, msg['networkId'], self.network_id))
        genesis = await self.genesis
        if msg['genesisHash'] != genesis.hash:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                "{} genesis ({}) does not match ours ({}), disconnecting".format(
                    self, encode_hex(msg['genesisHash']), genesis.hex_hash))
        # TODO: Disconnect if the remote doesn't serve headers.
        self.head_td = msg['headTd']
        self.head_hash = msg['headHash']
        self.head_number = msg['headNum']

    #
    # TODO: De-duplicate between this an ETHPeer class
    #
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


class LESPeerFactory(BasePeerFactory):
    peer_class = LESPeer
    context: ChainContext


class LESPeerPool(BasePeerPool):
    peer_factory_class = LESPeerFactory
    context: ChainContext
    connected_nodes: Dict[Node, LESPeer]  # type: ignore

    #
    # TODO: De-duplicate between this an ETHPeerPool class
    #
    @property
    def highest_td_peer(self) -> LESPeer:
        peers = tuple(self.connected_nodes.values())
        if not peers:
            raise NoConnectedPeers()
        peers_by_td = groupby(operator.attrgetter('head_td'), peers)
        max_td = max(peers_by_td.keys())
        return random.choice(peers_by_td[max_td])

    def get_peers(self, min_td: int) -> List[LESPeer]:
        # TODO: Consider turning this into a method that returns an AsyncIterator, to make it
        # harder for callsites to get a list of peers while making blocking calls, as those peers
        # might disconnect in the meantime.
        peers = tuple(self.connected_nodes.values())
        return [peer for peer in peers if peer.head_td >= min_td]
