import asyncio

import pytest

from p2p.protocol import Command, Protocol
from p2p.p2p_proto import Ping, Pong, P2PProtocol

from p2p.tools.factories import MultiplexerPairFactory


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


class UnknownProtocol(Protocol):
    name = 'unknown'
    version = 1
    _commands = (CommandC, CommandD)
    cmd_length = 2

    def send_cmd(self, cmd_type) -> None:
        header, body = self.cmd_by_type[cmd_type].encode({})
        self.transport.send(header, body)


@pytest.mark.asyncio
async def test_multiplexer_properties():
    multiplexer, _ = MultiplexerPairFactory(
        protocol_types=(SecondProtocol, ThirdProtocol),
    )
    transport = multiplexer.get_transport()

    base_protocol = multiplexer.get_protocol_by_type(P2PProtocol)
    second_protocol = multiplexer.get_protocol_by_type(SecondProtocol)
    third_protocol = multiplexer.get_protocol_by_type(ThirdProtocol)

    assert multiplexer.get_base_protocol() is base_protocol
    assert multiplexer.get_protocols() == (base_protocol, second_protocol, third_protocol)

    assert multiplexer.get_protocol_by_type(P2PProtocol) is base_protocol
    assert multiplexer.get_protocol_by_type(SecondProtocol) is second_protocol
    assert multiplexer.get_protocol_by_type(ThirdProtocol) is third_protocol

    assert multiplexer.has_protocol(P2PProtocol) is True
    assert multiplexer.has_protocol(SecondProtocol) is True
    assert multiplexer.has_protocol(ThirdProtocol) is True
    assert multiplexer.has_protocol(UnknownProtocol) is False

    assert multiplexer.has_protocol(base_protocol) is True
    assert multiplexer.has_protocol(second_protocol) is True
    assert multiplexer.has_protocol(third_protocol) is True
    assert multiplexer.has_protocol(UnknownProtocol(transport, 16, False)) is False

    assert multiplexer.remote is transport.remote


@pytest.mark.asyncio
async def test_multiplexer_only_p2p_protocol():
    alice_multiplexer, bob_multiplexer = MultiplexerPairFactory()

    async with alice_multiplexer.multiplex():
        async with bob_multiplexer.multiplex():
            alice_stream = alice_multiplexer.stream_protocol_messages(P2PProtocol)
            bob_stream = bob_multiplexer.stream_protocol_messages(P2PProtocol)

            alice_p2p_protocol = alice_multiplexer.get_protocol_by_type(P2PProtocol)
            bob_p2p_protocol = bob_multiplexer.get_protocol_by_type(P2PProtocol)

            alice_p2p_protocol.send_ping()
            cmd, _ = await asyncio.wait_for(bob_stream.asend(None), timeout=0.1)
            assert isinstance(cmd, Ping)

            bob_p2p_protocol.send_pong()
            cmd, _ = await asyncio.wait_for(alice_stream.asend(None), timeout=0.1)


@pytest.mark.asyncio
async def test_multiplexer_p2p_and_paragon_protocol():
    alice_multiplexer, bob_multiplexer = MultiplexerPairFactory(
        protocol_types=(SecondProtocol,),
    )

    async with alice_multiplexer.multiplex():
        async with bob_multiplexer.multiplex():
            alice_p2p_stream = alice_multiplexer.stream_protocol_messages(P2PProtocol)
            bob_p2p_stream = bob_multiplexer.stream_protocol_messages(P2PProtocol)
            alice_second_stream = alice_multiplexer.stream_protocol_messages(SecondProtocol)
            bob_second_stream = bob_multiplexer.stream_protocol_messages(SecondProtocol)

            alice_p2p_protocol = alice_multiplexer.get_protocol_by_type(P2PProtocol)
            alice_second_protocol = alice_multiplexer.get_protocol_by_type(SecondProtocol)

            bob_p2p_protocol = bob_multiplexer.get_protocol_by_type(P2PProtocol)
            bob_second_protocol = bob_multiplexer.get_protocol_by_type(SecondProtocol)

            alice_second_protocol.send_cmd(CommandA)
            alice_p2p_protocol.send_ping()
            alice_second_protocol.send_cmd(CommandB)
            cmd, _ = await asyncio.wait_for(bob_p2p_stream.asend(None), timeout=0.1)
            assert isinstance(cmd, Ping)

            bob_second_protocol.send_cmd(CommandA)
            bob_p2p_protocol.send_pong()
            bob_second_protocol.send_cmd(CommandB)

            cmd, _ = await asyncio.wait_for(alice_p2p_stream.asend(None), timeout=0.1)
            assert isinstance(cmd, Pong)

            cmd_1, _ = await asyncio.wait_for(bob_second_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_2, _ = await asyncio.wait_for(bob_second_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_3, _ = await asyncio.wait_for(alice_second_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_4, _ = await asyncio.wait_for(alice_second_stream.asend(None), timeout=0.1)  # noqa: E501

            assert isinstance(cmd_1, CommandA)
            assert isinstance(cmd_2, CommandB)
            assert isinstance(cmd_3, CommandA)
            assert isinstance(cmd_4, CommandB)


@pytest.mark.asyncio
async def test_multiplexer_p2p_and_two_more_protocols():
    alice_multiplexer, bob_multiplexer = MultiplexerPairFactory(
        protocol_types=(SecondProtocol, ThirdProtocol),
    )

    async with alice_multiplexer.multiplex():
        async with bob_multiplexer.multiplex():
            alice_p2p_stream = alice_multiplexer.stream_protocol_messages(P2PProtocol)
            bob_p2p_stream = bob_multiplexer.stream_protocol_messages(P2PProtocol)
            alice_second_stream = alice_multiplexer.stream_protocol_messages(SecondProtocol)
            bob_second_stream = bob_multiplexer.stream_protocol_messages(SecondProtocol)
            alice_third_stream = alice_multiplexer.stream_protocol_messages(ThirdProtocol)
            bob_third_stream = bob_multiplexer.stream_protocol_messages(ThirdProtocol)

            alice_p2p_protocol = alice_multiplexer.get_protocol_by_type(P2PProtocol)
            alice_second_protocol = alice_multiplexer.get_protocol_by_type(SecondProtocol)
            alice_third_protocol = alice_multiplexer.get_protocol_by_type(ThirdProtocol)

            bob_p2p_protocol = bob_multiplexer.get_protocol_by_type(P2PProtocol)
            bob_second_protocol = bob_multiplexer.get_protocol_by_type(SecondProtocol)
            bob_third_protocol = bob_multiplexer.get_protocol_by_type(ThirdProtocol)

            alice_second_protocol.send_cmd(CommandA)
            alice_third_protocol.send_cmd(CommandC)
            alice_p2p_protocol.send_ping()
            alice_second_protocol.send_cmd(CommandB)
            alice_third_protocol.send_cmd(CommandD)
            cmd, _ = await asyncio.wait_for(bob_p2p_stream.asend(None), timeout=0.1)
            assert isinstance(cmd, Ping)

            bob_second_protocol.send_cmd(CommandA)
            bob_third_protocol.send_cmd(CommandC)
            bob_p2p_protocol.send_pong()
            bob_second_protocol.send_cmd(CommandB)
            bob_third_protocol.send_cmd(CommandD)
            cmd, _ = await asyncio.wait_for(alice_p2p_stream.asend(None), timeout=0.1)
            assert isinstance(cmd, Pong)

            cmd_1, _ = await asyncio.wait_for(bob_third_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_2, _ = await asyncio.wait_for(bob_third_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_3, _ = await asyncio.wait_for(bob_second_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_4, _ = await asyncio.wait_for(bob_second_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_5, _ = await asyncio.wait_for(alice_third_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_6, _ = await asyncio.wait_for(alice_third_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_7, _ = await asyncio.wait_for(alice_second_stream.asend(None), timeout=0.1)  # noqa: E501
            cmd_8, _ = await asyncio.wait_for(alice_second_stream.asend(None), timeout=0.1)  # noqa: E501

            assert isinstance(cmd_1, CommandC)
            assert isinstance(cmd_2, CommandD)
            assert isinstance(cmd_3, CommandA)
            assert isinstance(cmd_4, CommandB)
            assert isinstance(cmd_5, CommandC)
            assert isinstance(cmd_6, CommandD)
            assert isinstance(cmd_7, CommandA)
            assert isinstance(cmd_8, CommandB)
