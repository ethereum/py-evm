import asyncio
import pytest

from p2p.p2p_proto import Ping
from p2p.behaviors import (
    Application,
    CommandHandler,
    ConnectionBehavior,
    command_handler,
)

from p2p.tools.factories import ConnectionPairFactory


@pytest.mark.asyncio
async def test_command_handler_behavior():
    got_ping = asyncio.Event()

    class HandlePing(CommandHandler):
        cmd_type = Ping

        async def handle(self, connection, msg):
            got_ping.set()

    async with ConnectionPairFactory() as (alice, bob):
        ping_handler = HandlePing()
        async with ping_handler.apply(alice):
            bob.get_base_protocol().send_ping()
            await asyncio.wait_for(got_ping.wait(), timeout=2)


@pytest.mark.asyncio
async def test_command_handler_decorator_behavior():
    got_ping = asyncio.Event()

    @command_handler(Ping)
    async def HandlePing(connection, msg):
        got_ping.set()

    async with ConnectionPairFactory() as (alice, bob):
        ping_handler = HandlePing()
        async with ping_handler.apply(alice):
            bob.get_base_protocol().send_ping()
            await asyncio.wait_for(got_ping.wait(), timeout=2)


@pytest.mark.asyncio
async def test_connection_behavior_helper():
    got_ping = asyncio.Event()

    class SendPing(ConnectionBehavior):
        def applies_to(self, connection):
            return True

        def __call__(self) -> None:
            self._connection.get_base_protocol().send_ping()

    async def handle_ping(connection, msg):
        got_ping.set()

    async with ConnectionPairFactory() as (alice, bob):
        bob.add_command_handler(Ping, handle_ping)
        send_ping = SendPing()

        async with send_ping.apply(alice):
            send_ping()
            await asyncio.wait_for(got_ping.wait(), timeout=2)


@pytest.mark.asyncio
async def test_behavior_application():
    got_ping = asyncio.Event()

    class SendPing(ConnectionBehavior):
        def applies_to(self, connection):
            return True

        def __call__(self) -> None:
            self._connection.get_base_protocol().send_ping()

    class HasSendPing(Application):
        name = 'ping-test'

        def __init__(self):
            self.send_ping = SendPing()

        def get_behaviors(self):
            return (self.send_ping,)

    async def handle_ping(connection, msg):
        got_ping.set()

    async with ConnectionPairFactory() as (alice, bob):
        bob.add_command_handler(Ping, handle_ping)

        # ensure the API isn't already registered
        assert not alice.has_behavior('ping-test')
        async with HasSendPing().apply(alice):
            # ensure it registers with the connect
            assert alice.has_behavior('ping-test')
            has_send_ping = alice.get_behavior('ping-test', HasSendPing)
            has_send_ping.send_ping()
            await asyncio.wait_for(got_ping.wait(), timeout=2)
        # ensure it removes itself from the API on exit
        assert not alice.has_behavior('ping-test')
