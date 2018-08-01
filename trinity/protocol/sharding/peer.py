import asyncio
from typing import (
    Any,
    cast,
    Dict,
    List,
    Set,
    Tuple,
)

from eth_typing import (
    BlockNumber,
    Hash32,
)

from cancel_token import CancelToken

from eth.rlp.collations import Collation
from eth.rlp.headers import BlockHeader

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

from p2p.exceptions import (
    HandshakeFailure,
    UnexpectedMessage,
)

from trinity.protocol.sharding.commands import (
    Collations,
    Status,
)
from trinity.protocol.sharding.proto import (
    ShardingProtocol,
)


class ShardingPeer(BasePeer):
    _supported_sub_protocols = [ShardingProtocol]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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
            await self.disconnect(DisconnectReason.subprotocol_error)
            raise HandshakeFailure("Expected status msg, got {}, disconnecting".format(cmd))

    async def _get_headers_at_chain_split(
            self, block_number: BlockNumber) -> Tuple[BlockHeader, BlockHeader]:
        pass

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
        from trinity.utils.les import gen_request_id
        # Don't send empty request
        if len(collation_hashes) == 0:
            return set()

        request_id = gen_request_id()
        pending_reply: asyncio.Future[Tuple[Command, protocol._DecodedMsgType]] = asyncio.Future()
        self._pending_replies[request_id] = pending_reply
        cast(ShardingProtocol, self.sub_proto).send_get_collations(request_id, collation_hashes)
        cmd, msg = await cancel_token.cancellable_wait(pending_reply)
        msg = cast(Dict[str, Any], msg)
        if not isinstance(cmd, Collations):
            raise UnexpectedMessage(
                "Expected Collations as response to GetCollations, but got %s",
                cmd.__class__.__name__
            )
        return set(msg["collations"])
