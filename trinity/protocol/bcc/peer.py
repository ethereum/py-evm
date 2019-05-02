from typing import (
    cast,
)

from eth_utils import (
    encode_hex,
)

from trinity.db.beacon.chain import BaseAsyncBeaconChainDB
from eth2.beacon.types.blocks import (
    BeaconBlock,
)

from eth2.beacon.typing import (
    Slot,
)

from p2p.peer import (
    BasePeer,
    BasePeerFactory,
)
from p2p.peer_pool import (
    BasePeerPool,
)
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)
from p2p.exceptions import HandshakeFailure
from p2p.p2p_proto import DisconnectReason

from trinity.protocol.bcc.handlers import BCCExchangeHandler

from trinity.protocol.bcc.proto import BCCProtocol
from trinity.protocol.bcc.commands import (
    Status,
    StatusMessage,
)
from trinity.protocol.bcc.context import (
    BeaconContext,
)


class BCCPeer(BasePeer):

    supported_sub_protocols = [BCCProtocol]
    sub_proto: BCCProtocol = None

    _requests: BCCExchangeHandler = None

    context: BeaconContext

    head_slot: Slot = None

    async def send_sub_proto_handshake(self) -> None:
        # TODO: pass accurate `block_class: Type[BaseBeaconBlock]` under per BeaconStateMachine fork
        genesis = await self.chain_db.coro_get_canonical_block_by_slot(
            self.context.genesis_slot,
            BeaconBlock,
        )
        head = await self.chain_db.coro_get_canonical_head(BeaconBlock)
        self.sub_proto.send_handshake(genesis.signing_root, head.slot)

    async def process_sub_proto_handshake(self, cmd: Command, msg: _DecodedMsgType) -> None:
        if not isinstance(cmd, Status):
            await self.disconnect(DisconnectReason.subprotocol_error)
            raise HandshakeFailure(f"Expected a BCC Status msg, got {cmd}, disconnecting")

        msg = cast(StatusMessage, msg)
        if msg['network_id'] != self.network_id:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                f"{self} network ({msg['network_id']}) does not match ours "
                f"({self.network_id}), disconnecting"
            )
        # TODO: pass accurate `block_class: Type[BaseBeaconBlock]` under per BeaconStateMachine fork
        genesis_block = await self.chain_db.coro_get_canonical_block_by_slot(
            self.context.genesis_slot,
            BeaconBlock,
        )
        # TODO change message descriptor to 'genesis_root', accounting for the spec
        if msg['genesis_hash'] != genesis_block.signing_root:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                f"{self} genesis ({encode_hex(msg['genesis_hash'])}) does not "
                f"match ours ({encode_hex(genesis_block.signing_root)}), disconnecting"
            )

        self.head_slot = msg['head_slot']

    @property
    def network_id(self) -> int:
        return self.context.network_id

    @property
    def chain_db(self) -> BaseAsyncBeaconChainDB:
        return self.context.chain_db

    @property
    def requests(self) -> BCCExchangeHandler:
        if self._requests is None:
            self._requests = BCCExchangeHandler(self)
        return self._requests


class BCCPeerFactory(BasePeerFactory):
    context: BeaconContext
    peer_class = BCCPeer


class BCCPeerPool(BasePeerPool):
    peer_factory_class = BCCPeerFactory
