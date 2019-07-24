import asyncio
import pytest

import rlp
from rlp import sedes

from p2p.tools.factories import (
    TransportPairFactory,
    MemoryTransportPairFactory,
    CancelTokenFactory,
)
from p2p.protocol import Command


class CommandForTest(Command):
    _cmd_id = 0
    structure = (
        ('data', sedes.binary),
    )


@pytest.fixture(params=('memory', 'real'))
async def transport_pair(request):
    if request.param == 'memory':
        return MemoryTransportPairFactory()
    elif request.param == 'real':
        return await TransportPairFactory()
    else:
        raise Exception(f"Unknown: {request.param}")


@pytest.mark.asyncio
async def test_transport_pair_factories(transport_pair):
    token = CancelTokenFactory()
    alice_transport, bob_transport = transport_pair

    done = asyncio.Event()

    async def manage_bob(expected):
        for msg in expected:
            data = await bob_transport.recv(token)
            assert msg == data
        done.set()

    messages = (
        b'unicorns',
        b'rainbows',
        b'',
        b'\x00' * 256,
        b'\x00' * 65536,
    )
    cmd = CommandForTest(5, False)
    rlp_messages = tuple(
        rlp.encode(cmd.cmd_id, sedes.big_endian_int) + rlp.encode((msg,))
        for msg in messages
    )
    asyncio.ensure_future(manage_bob(rlp_messages))
    for message in messages:
        header, body = cmd.encode({'data': message})
        alice_transport.send(header, body)

    await asyncio.wait_for(done.wait(), timeout=0.1)
