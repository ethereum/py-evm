import asyncio
from typing import Any

from p2p.abc import ConnectionAPI
from p2p.p2p_proto import Ping, Pong


async def do_ping_pong_test(alice_connection: ConnectionAPI, bob_connection: ConnectionAPI) -> None:
    got_ping = asyncio.Event()
    got_pong = asyncio.Event()

    async def _handle_ping(connection: ConnectionAPI, msg: Any) -> None:
        got_ping.set()
        bob_connection.get_base_protocol().send(Pong(None))

    async def _handle_pong(connection: ConnectionAPI, msg: Any) -> None:
        got_pong.set()

    alice_connection.add_command_handler(Pong, _handle_pong)
    bob_connection.add_command_handler(Ping, _handle_ping)

    alice_connection.get_base_protocol().send(Ping(None))

    await asyncio.wait_for(got_ping.wait(), timeout=1)
    await asyncio.wait_for(got_pong.wait(), timeout=1)
