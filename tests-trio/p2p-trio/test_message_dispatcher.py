import pytest

import pytest_trio

import trio

from p2p.trio_service import (
    background_service,
)

from p2p.tools.factories.discovery import (
    EndpointFactory,
    ENRFactory,
    PingMessageFactory,
)
from p2p.tools.factories.keys import (
    PrivateKeyFactory,
)

from p2p.discv5.enr_db import MemoryEnrDb
from p2p.discv5.channel_services import (
    IncomingMessage,
)
from p2p.discv5.identity_schemes import (
    default_identity_scheme_registry,
)
from p2p.discv5.messages import (
    PingMessage,
)
from p2p.discv5.message_dispatcher import (
    MessageDispatcher,
)


@pytest.fixture
def private_key():
    return PrivateKeyFactory().to_bytes()


@pytest.fixture
def remote_private_key():
    return PrivateKeyFactory().to_bytes()


@pytest.fixture
def endpoint():
    return EndpointFactory()


@pytest.fixture
def remote_endpoint():
    return EndpointFactory()


@pytest.fixture
def enr(private_key, endpoint):
    return ENRFactory(
        private_key=private_key,
        custom_kv_pairs={
            b"ip": endpoint.ip_address,
            b"udp": endpoint.port,
        }
    )


@pytest.fixture
def remote_enr(remote_private_key, remote_endpoint):
    return ENRFactory(
        private_key=remote_private_key,
        custom_kv_pairs={
            b"ip": remote_endpoint.ip_address,
            b"udp": remote_endpoint.port,
        }
    )


@pytest_trio.trio_fixture
async def enr_db(enr, remote_enr):
    db = MemoryEnrDb(default_identity_scheme_registry)
    await db.insert(enr)
    await db.insert(remote_enr)
    return db


@pytest.fixture
def incoming_message_channels():
    return trio.open_memory_channel(0)


@pytest.fixture
def outgoing_message_channels():
    return trio.open_memory_channel(0)


@pytest_trio.trio_fixture
async def message_dispatcher(enr_db, incoming_message_channels, outgoing_message_channels):
    message_dispatcher = MessageDispatcher(
        enr_db=enr_db,
        incoming_message_receive_channel=incoming_message_channels[1],
        outgoing_message_send_channel=outgoing_message_channels[0],
    )
    async with background_service(message_dispatcher):
        yield message_dispatcher


@pytest.mark.trio
async def test_request_handling(message_dispatcher,
                                incoming_message_channels,
                                remote_enr,
                                remote_endpoint):
    ping_send_channel, ping_receive_channel = trio.open_memory_channel(0)

    async with message_dispatcher.add_request_handler(
        PingMessage.message_type,
    ) as request_subscription:

        incoming_message = IncomingMessage(
            message=PingMessageFactory(),
            sender_endpoint=remote_endpoint,
            sender_node_id=remote_enr.node_id,
        )
        await incoming_message_channels[0].send(incoming_message)

        with trio.fail_after(1):
            handled_incoming_message = await request_subscription.receive()
        assert handled_incoming_message == incoming_message


@pytest.mark.trio
async def test_response_handling(message_dispatcher, remote_enr, incoming_message_channels):
    request_id = message_dispatcher.get_free_request_id(remote_enr.node_id)
    async with message_dispatcher.add_response_handler(
        remote_enr.node_id,
        request_id,
    ) as response_subscription:

        incoming_message = IncomingMessage(
            message=PingMessageFactory(
                request_id=request_id,
            ),
            sender_endpoint=remote_endpoint,
            sender_node_id=remote_enr.node_id,
        )
        await incoming_message_channels[0].send(incoming_message)

        with trio.fail_after(1):
            handled_response = await response_subscription.receive()
        assert handled_response == incoming_message


@pytest.mark.trio
async def test_request(message_dispatcher,
                       remote_enr,
                       remote_endpoint,
                       incoming_message_channels,
                       outgoing_message_channels,
                       nursery,
                       ):
    request_id = message_dispatcher.get_free_request_id(remote_enr.node_id)
    request = PingMessageFactory(request_id=request_id)
    response = PingMessageFactory(request_id=request_id)

    async def handle_request_on_remote():
        outgoing_message = await outgoing_message_channels[1].receive()
        assert outgoing_message.message == request
        assert outgoing_message.receiver_endpoint == remote_endpoint
        assert outgoing_message.receiver_node_id == remote_enr.node_id

        await incoming_message_channels[0].send(IncomingMessage(
            message=response,
            sender_endpoint=remote_endpoint,
            sender_node_id=remote_enr.node_id,
        ))

    nursery.start_soon(handle_request_on_remote)

    received_response = await message_dispatcher.request(remote_enr.node_id, request)

    assert received_response.message == response
    assert received_response.sender_endpoint == remote_endpoint
    assert received_response.sender_node_id == remote_enr.node_id
