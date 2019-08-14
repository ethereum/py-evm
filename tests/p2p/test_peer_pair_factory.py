import asyncio

import pytest

from p2p.tools.factories import ParagonPeerPairFactory


@pytest.mark.asyncio
async def test_connection_factory_with_ParagonPeer():
    async with ParagonPeerPairFactory() as (alice, bob):
        got_ping = asyncio.Event()
        got_pong = asyncio.Event()

        def handle_ping(cmd, msg):
            got_ping.set()
            bob.base_protocol.send_pong()

        def handle_pong(cmd, msg):
            got_pong.set()

        alice.handle_p2p_msg = handle_pong
        bob.handle_p2p_msg = handle_ping

        alice.base_protocol.send_ping()

        await asyncio.wait_for(got_ping.wait(), timeout=0.1)
        await asyncio.wait_for(got_pong.wait(), timeout=0.1)
