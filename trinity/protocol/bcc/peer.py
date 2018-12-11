from eth.beacon.db.chain import BaseBeaconChainDB

from p2p.peer import (
    BasePeer,
    BasePeerFactory,
    BasePeerPool,
)
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)
from p2p.exceptions import HandshakeFailure
from p2p.p2p_proto import DisconnectReason

from trinity.protocol.bcc.proto import BCCProtocol
from trinity.protocol.bcc.commands import (
    Status,
)
from trinity.protocol.bcc.context import (
    BeaconContext,
)

from eth_utils import (
    encode_hex,
)

from typing import (
    cast,
    Any,
    Dict,
)
from eth_typing import (
    Hash32,
)


class BCCPeer(BasePeer):

    _supported_sub_protocols = [BCCProtocol]
    sub_proto: BCCProtocol = None

    context: BeaconContext

    head_hash: Hash32 = None

    async def send_sub_proto_handshake(self) -> None:
        genesis = self.chain_db.get_canonical_block_by_slot(0)
        head = self.chain_db.get_canonical_head()
        self.sub_proto.send_handshake(genesis.hash, head.hash)

    async def process_sub_proto_handshake(self, cmd: Command, msg: _DecodedMsgType) -> None:
        if not isinstance(cmd, Status):
            await self.disconnect(DisconnectReason.subprotocol_error)
            raise HandshakeFailure(f"Expected a BCC Status msg, got {cmd}, disconnecting")

        msg = cast(Dict[str, Any], msg)
        if msg['network_id'] != self.network_id:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                f"{self} network ({msg['network_id']}) does not match ours "
                f"({self.network_id}), disconnecting"
            )

        genesis_block = self.chain_db.get_canonical_block_by_slot(0)
        if msg['genesis_hash'] != genesis_block.hash:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                f"{self} genesis ({encode_hex(msg['genesis_hash'])}) does not "
                f"match ours ({encode_hex(genesis_block.hash)}), disconnecting"
            )

        self.head_hash = msg['best_hash']

    @property
    def network_id(self) -> int:
        return self.context.network_id

    @property
    def chain_db(self) -> BaseBeaconChainDB:
        return self.context.chain_db


class BCCPeerFactory(BasePeerFactory):
    context: BeaconContext
    peer_class = BCCPeer


class BCCPeerPool(BasePeerPool):
    peer_factory_class = BCCPeerFactory
