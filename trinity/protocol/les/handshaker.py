from typing import (
    cast,
    Any,
    Dict,
    Type,
    Union,
)

from eth_utils import encode_hex

from p2p.abc import MultiplexerAPI, ProtocolAPI
from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.handshake import (
    HandshakeReceipt,
    Handshaker,
)

from trinity.exceptions import WrongGenesisFailure, WrongNetworkFailure

from .commands import Status, StatusV2

from .proto import LESHandshakeParams, LESProtocol, LESProtocolV2


AnyLESProtocol = Union[LESProtocol, LESProtocolV2]
AnyLESProtocolClass = Union[Type[LESProtocol], Type[LESProtocolV2]]


class LESHandshakeReceipt(HandshakeReceipt):
    handshake_params: LESHandshakeParams

    def __init__(self,
                 protocol: AnyLESProtocol,
                 handshake_params: LESHandshakeParams,
                 ) -> None:
        super().__init__(protocol)
        self.handshake_params = handshake_params


class BaseLESHandshaker(Handshaker):
    handshake_params: LESHandshakeParams

    def __init__(self, handshake_params: LESHandshakeParams) -> None:
        if handshake_params.version != self.protocol_class.version:
            raise Exception("DID NOT MATCH")
        self.handshake_params = handshake_params

    async def do_handshake(self,
                           multiplexer: MultiplexerAPI,
                           protocol: ProtocolAPI) -> LESHandshakeReceipt:
        """Perform the handshake for the sub-protocol agreed with the remote peer.

        Raises HandshakeFailure if the handshake is not successful.
        """
        protocol = cast(AnyLESProtocol, protocol)
        protocol.send_handshake(self.handshake_params)

        async for cmd, msg in multiplexer.stream_protocol_messages(protocol):
            if not isinstance(cmd, (Status, StatusV2)):
                raise HandshakeFailure(f"Expected a LES Status msg, got {cmd}, disconnecting")

            msg = cast(Dict[str, Any], msg)

            remote_params = LESHandshakeParams(
                version=msg['protocolVersion'],
                network_id=msg['networkId'],
                head_td=msg['headTd'],
                head_hash=msg['headHash'],
                head_num=msg['headNum'],
                genesis_hash=msg['genesisHash'],
                serve_headers=('serveHeaders' in msg),
                serve_chain_since=msg.get('serveChainSince'),
                serve_state_since=msg.get('serveStateSince'),
                serve_recent_chain=msg.get('serveRecentChain'),
                serve_recent_state=msg.get('serveRecentState'),
                tx_relay=('txRelay' in msg),
                flow_control_bl=msg.get('flowControl/BL'),
                flow_control_mcr=msg.get('flowControl/MRC'),
                flow_control_mrr=msg.get('flowControl/MRR'),
                announce_type=msg.get('announceType'),  # TODO: only in StatusV2
            )

            if remote_params.network_id != self.handshake_params.network_id:
                raise WrongNetworkFailure(
                    f"{multiplexer.remote} network "
                    f"({remote_params.network_id}) does not match ours "
                    f"({self.handshake_params.network_id}), disconnecting"
                )

            if remote_params.genesis_hash != self.handshake_params.genesis_hash:
                raise WrongGenesisFailure(
                    f"{multiplexer.remote} genesis "
                    f"({encode_hex(remote_params.genesis_hash)}) does "
                    f"not match ours "
                    f"({encode_hex(self.handshake_params.genesis_hash)}), "
                    f"disconnecting"
                )

            # Eventually we might want to keep connections to peers where we
            # are the only side serving data, but right now both our chain
            # syncer and the Peer.boot() method expect the remote to reply to
            # header requests, so if they don't we simply disconnect here.
            if remote_params.serve_headers is False:
                raise HandshakeFailure(f"{multiplexer.remote} doesn't serve headers, disconnecting")

            receipt = LESHandshakeReceipt(protocol, remote_params)
            break
        else:
            raise HandshakeFailure("Message stream exited before finishing handshake")

        return receipt


class LESV1Handshaker(BaseLESHandshaker):
    protocol_class = LESProtocol


class LESV2Handshaker(BaseLESHandshaker):
    protocol_class = LESProtocolV2
