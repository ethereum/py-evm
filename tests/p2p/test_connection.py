import asyncio

import pytest

from p2p.constants import DEVP2P_V4, DEVP2P_V5
from p2p.p2p_proto import P2PProtocolV4, Ping
from p2p.protocol import Command, Protocol
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

        async def _handle_ping(conn, msg):
            got_ping.set()

        alice_connection.add_command_handler(Ping, _handle_ping)

        bob_base_protocol = bob_connection.get_base_protocol()
        bob_base_protocol.send_ping()

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


class CommandA(Command):
    _cmd_id = 0
    structure = ()


class CommandB(Command):
    _cmd_id = 1
    structure = ()


class SecondProtocol(Protocol):
    name = 'second'
    version = 1
    _commands = (CommandA, CommandB)
    cmd_length = 2

    def send_cmd(self, cmd_type) -> None:
        header, body = self.cmd_by_type[cmd_type].encode({})
        self.transport.send(header, body)


class CommandC(Command):
    _cmd_id = 0
    structure = ()


class CommandD(Command):
    _cmd_id = 1
    structure = ()


class ThirdProtocol(Protocol):
    name = 'third'
    version = 1
    _commands = (CommandC, CommandD)
    cmd_length = 2

    def send_cmd(self, cmd_type) -> None:
        header, body = self.cmd_by_type[cmd_type].encode({})
        self.transport.send(header, body)


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

        async def _handler_second_protocol(conn, cmd, msg):
            messages_second_protocol.append((cmd, msg))

        async def _handler_cmd_A(conn, msg):
            messages_cmd_A.append(msg)

        async def _handler_cmd_D(conn, msg):
            messages_cmd_D.append(msg)

        async def _handler_cmd_C(conn, msg):
            done.set()

        alice_connection.add_protocol_handler(SecondProtocol, _handler_second_protocol)
        alice_connection.add_command_handler(CommandA, _handler_cmd_A)
        alice_connection.add_command_handler(CommandC, _handler_cmd_C)
        alice_connection.add_command_handler(CommandD, _handler_cmd_D)

        alice_connection.start_protocol_streams()
        bob_connection.start_protocol_streams()

        bob_second_protocol = bob_connection.get_multiplexer().get_protocol_by_type(SecondProtocol)
        bob_third_protocol = bob_connection.get_multiplexer().get_protocol_by_type(ThirdProtocol)

        bob_second_protocol.send_cmd(CommandA)
        bob_second_protocol.send_cmd(CommandB)
        bob_third_protocol.send_cmd(CommandD)
        bob_second_protocol.send_cmd(CommandB)
        bob_third_protocol.send_cmd(CommandD)
        bob_second_protocol.send_cmd(CommandA)
        bob_second_protocol.send_cmd(CommandB)
        bob_third_protocol.send_cmd(CommandD)
        bob_third_protocol.send_cmd(CommandC)

        await asyncio.wait_for(done.wait(), timeout=1)

        assert len(messages_second_protocol) == 5
        assert len(messages_cmd_A) == 2
        assert len(messages_cmd_D) == 3
