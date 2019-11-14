import asyncio
import pytest

from rlp import sedes

from p2p.tools.factories import (
    TransportPairFactory,
    MemoryTransportPairFactory,
    CancelTokenFactory,
)
from p2p.commands import BaseCommand, RLPCodec


class CommandForTest(BaseCommand[bytes]):
    protocol_command_id = 0
    serialization_codec = RLPCodec(sedes=sedes.binary)


@pytest.fixture(params=('memory', 'real'))
async def transport_pair(request):
    if request.param == 'memory':
        return MemoryTransportPairFactory()
    elif request.param == 'real':
        return await TransportPairFactory()
    else:
        raise Exception(f"Unknown: {request.param}")


@pytest.mark.parametrize('snappy_support', (True, False))
@pytest.mark.asyncio
async def test_transport_pair_factories(transport_pair, snappy_support):
    token = CancelTokenFactory()
    alice_transport, bob_transport = transport_pair

    done = asyncio.Event()

    async def manage_bob(expected):
        for value in expected:
            msg = await bob_transport.recv(token)
            assert msg == value
        done.set()

    payloads = (
        b'unicorns',
        b'rainbows',
        b'',
        b'\x00' * 256,
        b'\x00' * 65536,
    )
    messages = tuple(
        CommandForTest(payload).encode(
            CommandForTest.protocol_command_id,
            snappy_support=snappy_support,
        ) for payload in payloads
    )
    asyncio.ensure_future(manage_bob(messages))
    for payload in payloads:
        command = CommandForTest(payload)
        message = command.encode(CommandForTest.protocol_command_id, snappy_support=snappy_support)
        alice_transport.send(message)

    await asyncio.wait_for(done.wait(), timeout=1)
