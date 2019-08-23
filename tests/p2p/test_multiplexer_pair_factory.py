import pytest

from p2p.constants import DEVP2P_V4, DEVP2P_V5
from p2p.p2p_proto import P2PProtocol, P2PProtocolV4
from p2p.tools.factories import MultiplexerPairFactory, NodeFactory


def test_multiplexer_pair_factory():
    alice_remote, bob_remote = NodeFactory.create_batch(2)
    alice_multiplexer, bob_multiplexer = MultiplexerPairFactory(
        alice_remote=alice_remote,
        bob_remote=bob_remote,
    )
    assert alice_multiplexer.remote == bob_remote
    assert bob_multiplexer.remote == alice_remote

    assert alice_multiplexer.get_base_protocol().version == DEVP2P_V5
    assert bob_multiplexer.get_base_protocol().version == DEVP2P_V5


@pytest.mark.parametrize(
    'alice_p2p_version,bob_p2p_version,expected_base_protocol_class',
    (
        (DEVP2P_V4, DEVP2P_V4, P2PProtocolV4),
        (DEVP2P_V4, DEVP2P_V5, P2PProtocolV4),
        (DEVP2P_V5, DEVP2P_V4, P2PProtocolV4),
        (DEVP2P_V5, DEVP2P_V5, P2PProtocol),
    ),
)
@pytest.mark.asyncio
async def test_multiplexer_pair_factory_with_different_p2p_versions(
    alice_p2p_version,
    bob_p2p_version,
    expected_base_protocol_class,
):
    alice_multiplexer, bob_multiplexer = MultiplexerPairFactory(
        alice_p2p_version=alice_p2p_version,
        bob_p2p_version=bob_p2p_version,
    )
    alice_base_protocol = alice_multiplexer.get_base_protocol()
    bob_base_protocol = bob_multiplexer.get_base_protocol()

    assert type(alice_base_protocol) is expected_base_protocol_class
    assert type(bob_base_protocol) is expected_base_protocol_class

    assert alice_base_protocol.version == expected_base_protocol_class.version
    assert bob_base_protocol.version == expected_base_protocol_class.version
