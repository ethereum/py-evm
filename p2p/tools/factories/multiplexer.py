from typing import Callable, Tuple, Type

from cancel_token import CancelToken

from eth_keys import keys

from p2p.abc import MultiplexerAPI, NodeAPI, ProtocolAPI, TransportAPI
from p2p.multiplexer import Multiplexer
from p2p.p2p_proto import P2PProtocol
from p2p.protocol import get_cmd_offsets

from .transport import MemoryTransportPairFactory


TransportPair = Tuple[
    TransportAPI,
    TransportAPI,
]


def MultiplexerPairFactory(*,
                           protocol_types: Tuple[Type[ProtocolAPI], ...] = (),
                           transport_factory: Callable[..., TransportPair] = MemoryTransportPairFactory,  # noqa: E501
                           alice_remote: NodeAPI = None,
                           alice_private_key: keys.PrivateKey = None,
                           bob_remote: NodeAPI = None,
                           bob_private_key: keys.PrivateKey = None,
                           snappy_support: bool = False,
                           cancel_token: CancelToken = None,
                           ) -> Tuple[MultiplexerAPI, MultiplexerAPI]:
    alice_transport, bob_transport = transport_factory(
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
    )
    cmd_id_offsets = get_cmd_offsets(protocol_types)
    alice_protocols = tuple(
        protocol_class(alice_transport, offset, snappy_support)
        for protocol_class, offset
        in zip(protocol_types, cmd_id_offsets)
    )
    bob_protocols = tuple(
        protocol_class(bob_transport, offset, snappy_support)
        for protocol_class, offset
        in zip(protocol_types, cmd_id_offsets)
    )

    alice_p2p_protocol = P2PProtocol(alice_transport, 0, snappy_support)
    alice_multiplexer = Multiplexer(
        transport=alice_transport,
        base_protocol=alice_p2p_protocol,
        protocols=alice_protocols,
        token=cancel_token,
    )

    bob_p2p_protocol = P2PProtocol(bob_transport, 0, snappy_support)
    bob_multiplexer = Multiplexer(
        transport=bob_transport,
        base_protocol=bob_p2p_protocol,
        protocols=bob_protocols,
        token=cancel_token,
    )
    return alice_multiplexer, bob_multiplexer
