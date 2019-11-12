import itertools

import pytest

from p2p.disconnect import DisconnectReason
from p2p.p2p_proto import (
    Hello,
    Ping,
    Pong,
    Disconnect,
    P2PProtocolV4,
    P2PProtocolV5,
)
from p2p.tools.factories import (
    CancelTokenFactory,
    HelloPayloadFactory,
    MemoryTransportPairFactory,
)


@pytest.mark.parametrize(
    'command_type,payload',
    (
        (Ping, None),
        (Pong, None),
    ) + tuple(itertools.product(
        (Disconnect,),
        DisconnectReason,
    )) + (
        (Hello, HelloPayloadFactory()),
    ),
)
@pytest.mark.parametrize(
    'snappy_support',
    (True, False),
)
def test_p2p_command_encode_and_decode_round_trips(command_type, payload, snappy_support):
    cmd = command_type(payload)
    message = cmd.encode(command_type.protocol_command_id, snappy_support=snappy_support)
    # the reason the command ID's match here is because the base `p2p` protocol
    # uses an offset of 0
    assert message.command_id == command_type.protocol_command_id
    result = command_type.decode(message, snappy_support=snappy_support)
    assert isinstance(result, command_type)
    assert result.payload == payload


@pytest.mark.parametrize(
    'command_type_and_payload',
    (
        (Hello, HelloPayloadFactory()),
        (Ping, None),
        (Pong, None),
    ) + tuple(itertools.product(
        (Disconnect,),
        DisconnectReason,
    )),
)
@pytest.mark.parametrize(
    'protocol_class',
    (P2PProtocolV4, P2PProtocolV5),
)
@pytest.mark.parametrize(
    'snappy_support',
    (True, False),
)
@pytest.mark.asyncio
async def test_round_trip_over_wire(command_type_and_payload, snappy_support, protocol_class):
    command_type, payload = command_type_and_payload

    alice, bob = MemoryTransportPairFactory()

    if protocol_class is P2PProtocolV4 and snappy_support is True:
        # "V4 of the p2p protocol doesn't support snappy compression"
        with pytest.raises(TypeError):
            protocol_class(alice, 0, snappy_support=snappy_support)
        return

    alice_p2p_proto = protocol_class(alice, 0, snappy_support=snappy_support)

    cmd = command_type(payload)
    alice_p2p_proto.send(cmd)

    msg = await bob.recv(CancelTokenFactory())
    assert msg.command_id == command_type.protocol_command_id
    result = command_type.decode(msg, snappy_support=snappy_support)
    assert isinstance(result, command_type)
    assert result.payload == payload
