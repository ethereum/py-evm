import asyncio
import pytest

from rlp import sedes

from p2p.tools.factories import (
    MemoryTransportPairFactory,
    CancelTokenFactory,
)
from p2p.commands import BaseCommand, RLPCodec


class CommandForTest(BaseCommand):
    protocol_command_id = 0
    serialization_codec = RLPCodec(sedes=sedes.binary)


@pytest.mark.parametrize('snappy_support', (True, False))
@pytest.mark.asyncio
async def test_memory_transport_tool(snappy_support):
    token = CancelTokenFactory()
    alice_transport, bob_transport = MemoryTransportPairFactory()

    command = CommandForTest(b'test-payload')
    message = command.encode(0, snappy_support)
    alice_transport.send(message)

    result = await asyncio.wait_for(bob_transport.recv(token), timeout=1)
    assert result == message
    result_command = CommandForTest.decode(result, snappy_support)

    assert result_command.payload == b'test-payload'
