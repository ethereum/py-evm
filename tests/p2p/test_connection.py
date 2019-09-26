import asyncio

import pytest

from p2p.constants import DEVP2P_V4, DEVP2P_V5
from p2p.p2p_proto import P2PProtocolV4, Ping
from p2p.commands import BaseCommand, NoneSerializationCodec
from p2p.protocol import BaseProtocol
from p2p.tools.connection import do_ping_pong_test
from p2p.tools.handshake import NoopHandshaker
from p2p.tools.factories import (
    ConnectionPairFactory,
    NodeFactory,
    PrivateKeyFactory,
    ProtocolFactory,
)


@pytest.mark.asyncio
async def test_connection_ping_and_pong():
    async with ConnectionPairFactory() as (alice_connection, bob_connection):
        await do_ping_pong_test(alice_connection, bob_connection)


@pytest.mark.asyncio
async def test_connection_waits_to_feed_protocol_streams():
    async with ConnectionPairFactory(start_streams=False) as (alice_connection, bob_connection):
        got_ping = asyncio.Event()

        async def _handle_ping(conn, cmd):
            got_ping.set()

        alice_connection.add_command_handler(Ping, _handle_ping)

        bob_base_protocol = bob_connection.get_base_protocol()
        bob_base_protocol.send(Ping(None))

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(got_ping.wait(), timeout=0.1)

        alice_connection.start_protocol_streams()

        await asyncio.wait_for(got_ping.wait(), timeout=1)


@pytest.mark.asyncio
async def test_connection_properties():
    Protocol_A = ProtocolFactory()
    Protocol_B = ProtocolFactory()

    alice_handshakers = (NoopHandshaker(Protocol_A),)
    bob_handshakers = (NoopHandshaker(Protocol_A), NoopHandshaker(Protocol_B))
    bob_capabilities = (Protocol_A.as_capability(), Protocol_B.as_capability())

    bob_remote = NodeFactory()
    bob_private_key = PrivateKeyFactory()

    pair_factory = ConnectionPairFactory(
        alice_handshakers=alice_handshakers,
        bob_handshakers=bob_handshakers,
        alice_p2p_version=DEVP2P_V4,
        bob_client_version='bob-client',
        bob_p2p_version=DEVP2P_V5,
        bob_private_key=bob_private_key,
        bob_remote=bob_remote,
    )
    async with pair_factory as (connection, _):
        assert type(connection.get_base_protocol()) is P2PProtocolV4
        assert connection.remote_capabilities == bob_capabilities
        assert connection.remote_p2p_version == DEVP2P_V5
        assert connection.negotiated_p2p_version == DEVP2P_V4
        assert connection.remote_public_key == bob_private_key.public_key
        assert connection.client_version_string == 'bob-client'
        assert connection.safe_client_version_string == 'bob-client'


@pytest.mark.asyncio
async def test_connection_safe_client_version_string():
    long_client_version_string = 'unicorns\nand\nrainbows\n' * 100
    pair_factory = ConnectionPairFactory(
        bob_client_version=long_client_version_string,
    )
    async with pair_factory as (connection, _):
        assert connection.client_version_string == long_client_version_string
        assert len(connection.safe_client_version_string) < len(long_client_version_string)
        assert '...' in connection.safe_client_version_string


class CommandA(BaseCommand):
    protocol_command_id = 0
    serialization_codec = NoneSerializationCodec()


class CommandB(BaseCommand):
    protocol_command_id = 1
    serialization_codec = NoneSerializationCodec()


class SecondProtocol(BaseProtocol):
    name = 'second'
    version = 1
    commands = (CommandA, CommandB)
    command_length = 2


class CommandC(BaseCommand):
    protocol_command_id = 0
    serialization_codec = NoneSerializationCodec()


class CommandD(BaseCommand):
    protocol_command_id = 1
    serialization_codec = NoneSerializationCodec()


class ThirdProtocol(BaseProtocol):
    name = 'third'
    version = 1
    commands = (CommandC, CommandD)
    command_length = 2


@pytest.mark.asyncio
async def test_connection_protocol_and_command_handlers():
    alice_handshakers = (NoopHandshaker(SecondProtocol), NoopHandshaker(ThirdProtocol))
    bob_handshakers = (NoopHandshaker(SecondProtocol), NoopHandshaker(ThirdProtocol))
    pair_factory = ConnectionPairFactory(
        alice_handshakers=alice_handshakers,
        bob_handshakers=bob_handshakers,
    )
    async with pair_factory as (alice_connection, bob_connection):
        messages_cmd_A = []
        messages_cmd_D = []
        messages_second_protocol = []

        done = asyncio.Event()

        async def _handler_second_protocol(conn, cmd):
            messages_second_protocol.append(cmd)

        async def _handler_cmd_A(conn, cmd):
            messages_cmd_A.append(cmd)

        async def _handler_cmd_D(conn, cmd):
            messages_cmd_D.append(cmd)

        async def _handler_cmd_C(conn, cmd):
            done.set()

        alice_connection.add_protocol_handler(SecondProtocol, _handler_second_protocol)
        alice_connection.add_command_handler(CommandA, _handler_cmd_A)
        alice_connection.add_command_handler(CommandC, _handler_cmd_C)
        alice_connection.add_command_handler(CommandD, _handler_cmd_D)

        alice_connection.start_protocol_streams()
        bob_connection.start_protocol_streams()

        bob_second_protocol = bob_connection.get_protocol_by_type(SecondProtocol)
        bob_third_protocol = bob_connection.get_protocol_by_type(ThirdProtocol)

        bob_second_protocol.send(CommandA(None))
        bob_second_protocol.send(CommandB(None))
        bob_third_protocol.send(CommandD(None))
        bob_second_protocol.send(CommandB(None))
        bob_third_protocol.send(CommandD(None))
        bob_second_protocol.send(CommandA(None))
        bob_second_protocol.send(CommandB(None))
        bob_third_protocol.send(CommandD(None))
        bob_third_protocol.send(CommandC(None))

        await asyncio.wait_for(done.wait(), timeout=1)

        assert len(messages_second_protocol) == 5
        assert len(messages_cmd_A) == 2
        assert len(messages_cmd_D) == 3
