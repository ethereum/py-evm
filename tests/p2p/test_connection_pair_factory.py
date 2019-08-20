import pytest

from p2p.constants import DEVP2P_V4, DEVP2P_V5
from p2p.p2p_proto import P2PProtocol, P2PProtocolV4
from p2p.tools.factories import ConnectionPairFactory, ProtocolFactory
from p2p.tools.connection import do_ping_pong_test
from p2p.tools.handshake import NoopHandshaker


@pytest.mark.asyncio
async def test_connection_pair_factory_with_no_protocols():
    async with ConnectionPairFactory() as (alice_connection, bob_connection):
        assert alice_connection.remote_capabilities == ()
        assert bob_connection.remote_capabilities == ()

        await do_ping_pong_test(alice_connection, bob_connection)


@pytest.mark.parametrize(
    'alice_p2p_version,bob_p2p_version',
    (
        (DEVP2P_V4, DEVP2P_V4),
        (DEVP2P_V4, DEVP2P_V5),
        (DEVP2P_V5, DEVP2P_V4),
        (DEVP2P_V5, DEVP2P_V5),
    ),
)
@pytest.mark.asyncio
async def test_connection_pair_factory_no_protocols_with_different_p2p_versions(
    alice_p2p_version,
    bob_p2p_version,
):
    pair_factory = ConnectionPairFactory(
        alice_p2p_version=alice_p2p_version,
        bob_p2p_version=bob_p2p_version,
    )
    async with pair_factory as (alice_connection, bob_connection):
        expected_base_protocol_version = min(alice_p2p_version, bob_p2p_version)
        if expected_base_protocol_version == DEVP2P_V4:
            expected_base_protocol_class = P2PProtocolV4
        elif expected_base_protocol_version == DEVP2P_V5:
            expected_base_protocol_class = P2PProtocol
        else:
            raise Exception(f"unrecognized version: {expected_base_protocol_version}")

        alice_base_protocol = alice_connection.get_base_protocol()
        bob_base_protocol = bob_connection.get_base_protocol()

        assert type(alice_base_protocol) is expected_base_protocol_class
        assert type(bob_base_protocol) is expected_base_protocol_class

        assert alice_base_protocol.version == expected_base_protocol_version
        assert bob_base_protocol.version == expected_base_protocol_version

        assert alice_connection.remote_p2p_version == bob_p2p_version
        assert bob_connection.remote_p2p_version == alice_p2p_version

        await do_ping_pong_test(alice_connection, bob_connection)


@pytest.mark.asyncio
async def test_connection_pair_factory_with_single_protocol():
    protocol_class = ProtocolFactory()

    alice_handshaker = NoopHandshaker(protocol_class)
    bob_handshaker = NoopHandshaker(protocol_class)

    pair_factory = ConnectionPairFactory(
        alice_handshakers=(alice_handshaker,),
        bob_handshakers=(bob_handshaker,),
    )

    async with pair_factory as (alice_connection, bob_connection):
        expected_caps = (protocol_class.as_capability(),)

        assert alice_connection.remote_capabilities == expected_caps
        assert bob_connection.remote_capabilities == expected_caps

        await do_ping_pong_test(alice_connection, bob_connection)


@pytest.mark.asyncio
async def test_connection_pair_factory_with_multiple_protocols():
    protocol_class_a = ProtocolFactory()
    protocol_class_b = ProtocolFactory()

    alice_handshaker_a = NoopHandshaker(protocol_class_a)
    alice_handshaker_b = NoopHandshaker(protocol_class_b)
    bob_handshaker_a = NoopHandshaker(protocol_class_a)
    bob_handshaker_b = NoopHandshaker(protocol_class_b)

    pair_factory = ConnectionPairFactory(
        alice_handshakers=(alice_handshaker_a, alice_handshaker_b),
        bob_handshakers=(bob_handshaker_a, bob_handshaker_b),
    )

    async with pair_factory as (alice_connection, bob_connection):
        expected_caps = (
            protocol_class_a.as_capability(),
            protocol_class_b.as_capability(),
        )
        assert alice_connection.remote_capabilities == expected_caps
        assert bob_connection.remote_capabilities == expected_caps

        await do_ping_pong_test(alice_connection, bob_connection)
