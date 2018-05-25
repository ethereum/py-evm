import asyncio
from typing import (
    cast,
    Dict,
    List,
    Set,
    Tuple,
)

from eth_typing import (
    Hash32,
)

from evm.rlp.collations import Collation

from p2p.cancel_token import (
    CancelToken,
    wait_with_token,
)
from p2p import protocol
from p2p.protocol import (
    Command,
)
from p2p.peer import (
    BasePeer,
)
from p2p.p2p_proto import (
    DisconnectReason,
)

from p2p.sharding_protocol import (
    ShardingProtocol,
    Collations,
    Status,
)

from p2p.utils import (
    gen_request_id,
)
from p2p.exceptions import (
    HandshakeFailure,
    UnexpectedMessage,
)


class ShardingPeer(BasePeer):
    _supported_sub_protocols = [ShardingProtocol]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.known_collation_hashes: Set[Hash32] = set()
        self._pending_replies: Dict[
            int,
            asyncio.Future[Tuple[Command, protocol._DecodedMsgType]]
        ] = {}

    #
    # Handshake
    #
    async def send_sub_proto_handshake(self) -> None:
        cast(ShardingProtocol, self.sub_proto).send_handshake()

    async def process_sub_proto_handshake(self,
                                          cmd: Command,
                                          msg: protocol._DecodedMsgType) -> None:
        if not isinstance(cmd, Status):
            self.disconnect(DisconnectReason.other)
            raise HandshakeFailure("Expected status msg, got {}, disconnecting".format(cmd))

    #
    # Message handling
    #
    def handle_sub_proto_msg(self, cmd: Command, msg: protocol._DecodedMsgType) -> None:
        if isinstance(msg, dict):
            request_id = msg.get("request_id")
            if request_id is not None and request_id in self._pending_replies:
                # This is a reply we're waiting for, so we consume it by resolving the registered
                # future
                future = self._pending_replies.pop(request_id)
                future.set_result((cmd, msg))
                return
        super().handle_sub_proto_msg(cmd, msg)

    #
    # Requests
    #
    async def get_collations(self,
                             collation_hashes: List[Hash32],
                             cancel_token: CancelToken) -> Set[Collation]:
        # Don't send empty request
        if len(collation_hashes) == 0:
            return set()

        request_id = gen_request_id()
        pending_reply: asyncio.Future[Tuple[Command, protocol._DecodedMsgType]] = asyncio.Future()
        self._pending_replies[request_id] = pending_reply
        cast(ShardingProtocol, self.sub_proto).send_get_collations(request_id, collation_hashes)
        cmd, msg = await wait_with_token(pending_reply, token=cancel_token)

        if not isinstance(cmd, Collations):
            raise UnexpectedMessage(
                "Expected Collations as response to GetCollations, but got %s",
                cmd.__class__.__name__
            )
        return set(msg["collations"])
