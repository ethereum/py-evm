from typing import (
    Any,
    cast,
    Dict,
    List,
    NamedTuple,
    Set,
)

from eth_utils import encode_hex

from p2p.exceptions import HandshakeFailure
from p2p.p2p_proto import DisconnectReason
from p2p.peer import BasePeer, PeerSubscriber
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)
from p2p.service import BaseService

from .commands import (
    NewBlock,
    Status,
)
from trinity.protocol.eth import constants
from .proto import ETHProtocol
from .handlers import ETHExchangeHandler


class ETHPeer(BasePeer):
    max_headers_fetch = constants.MAX_HEADERS_FETCH

    _supported_sub_protocols = [ETHProtocol]
    sub_proto: ETHProtocol = None

    _requests: ETHExchangeHandler = None

    def get_extra_stats(self) -> List[str]:
        stats_pairs = self.requests.get_stats().items()
        return ['%s: %s' % (cmd_name, stats) for cmd_name, stats in stats_pairs]

    @property
    def requests(self) -> ETHExchangeHandler:
        if self._requests is None:
            self._requests = ETHExchangeHandler(self)
        return self._requests

    def handle_sub_proto_msg(self, cmd: Command, msg: _DecodedMsgType) -> None:
        if isinstance(cmd, NewBlock):
            msg = cast(Dict[str, Any], msg)
            header, _, _ = msg['block']
            actual_head = header.parent_hash
            actual_td = msg['total_difficulty'] - header.difficulty
            if actual_td > self.head_td:
                self.head_hash = actual_head
                self.head_td = actual_td

        super().handle_sub_proto_msg(cmd, msg)

    async def send_sub_proto_handshake(self) -> None:
        self.sub_proto.send_handshake(await self._local_chain_info)

    async def process_sub_proto_handshake(
            self, cmd: Command, msg: _DecodedMsgType) -> None:
        if not isinstance(cmd, Status):
            await self.disconnect(DisconnectReason.subprotocol_error)
            raise HandshakeFailure(
                "Expected a ETH Status msg, got {}, disconnecting".format(cmd))
        msg = cast(Dict[str, Any], msg)
        if msg['network_id'] != self.network_id:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                "{} network ({}) does not match ours ({}), disconnecting".format(
                    self, msg['network_id'], self.network_id))
        genesis = await self.genesis
        if msg['genesis_hash'] != genesis.hash:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                "{} genesis ({}) does not match ours ({}), disconnecting".format(
                    self, encode_hex(msg['genesis_hash']), genesis.hex_hash))
        self.head_td = msg['td']
        self.head_hash = msg['best_hash']


class NewBlockMsg(NamedTuple):
    header: BlockHeader



class ChainHeadTracker(BaseService, PeerSubscriber):
    #
    # PeerSubscriber
    #
    subscription_msg_types: Set[Type[Command]] = {NewBlock}

    msg_queue_maxsize = 100

    def __init__(self, peer: ETHPeer) -> None:
        self.peer = peer

    async def _run(self) -> None:
        self.logger.debug("Launching %s for peer %s", self.__class__.__name__, self._peer)

        with self.subscribe_peer(self._peer):
            while self.is_operational:
                peer, cmd, msg = await self.wait(self.msg_queue.get())

                if isinstance(cmd, NewBlock):
                    msg = cast(Dict[str, Any], msg)
                    header, _, _ = msg['block']
                    td = msg['total_difficulty']

                    await self._maybe_update_chain(header, td)
                else:
                    self.logger.warning("Unexpected payload type: %s", cmd.__class__.__name__)

    # ordered list of 2-tuples of (header, td)
    recent_chain: List[Tuple[BlockHeader, int]]

    async def _initialize_recent_chain(self) -> None:
        for

    async def _maybe_update_chain(self, header: BlockHeader, td: int) -> None:
