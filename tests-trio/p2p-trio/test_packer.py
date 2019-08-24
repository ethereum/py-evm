import pytest

import trio

import pytest_trio

from p2p.trio_service import (
    background_service,
)

from p2p.discv5.channel_services import (
    IncomingPacket,
    OutgoingMessage,
)
from p2p.discv5.enr_db import (
    MemoryEnrDb,
)
from p2p.discv5.messages import (
    default_message_type_registry,
)
from p2p.discv5.identity_schemes import (
    default_identity_scheme_registry,
)
from p2p.discv5.packer import (
    Packer,
    PeerPacker,
)
from p2p.discv5.packets import (
    AuthHeaderPacket,
    AuthTagPacket,
    WhoAreYouPacket,
)
from p2p.discv5.tags import (
    compute_tag,
)

from p2p.tools.factories.discovery import (
    AuthTagPacketFactory,
    ENRFactory,
    EndpointFactory,
    HandshakeRecipientFactory,
    PingMessageFactory,
)
from p2p.tools.factories.keys import (
    PrivateKeyFactory,
)


@pytest.fixture
def private_key():
    return PrivateKeyFactory().to_bytes()


@pytest.fixture
def remote_private_key():
    return PrivateKeyFactory().to_bytes()


@pytest.fixture
def enr(private_key):
    return ENRFactory(private_key=private_key)


@pytest.fixture
def remote_enr(remote_private_key):
    return ENRFactory(private_key=remote_private_key)


@pytest.fixture
def endpoint():
    return EndpointFactory()


@pytest.fixture
def remote_endpoint():
    return EndpointFactory()


@pytest_trio.trio_fixture
async def enr_db(enr, remote_enr):
    db = MemoryEnrDb(default_identity_scheme_registry)
    await db.insert(enr)
    await db.insert(remote_enr)
    return db


@pytest.fixture
def incoming_packet_channels():
    return trio.open_memory_channel(0)


@pytest.fixture
def incoming_message_channels():
    return trio.open_memory_channel(1)


@pytest.fixture
def outgoing_packet_channels():
    return trio.open_memory_channel(1)


@pytest.fixture
def outgoing_message_channels():
    return trio.open_memory_channel(1)


@pytest.fixture
def remote_incoming_packet_channels():
    return trio.open_memory_channel(1)


@pytest.fixture
def remote_incoming_message_channels():
    return trio.open_memory_channel(1)


@pytest.fixture
def remote_outgoing_packet_channels():
    return trio.open_memory_channel(1)


@pytest.fixture
def remote_outgoing_message_channels():
    return trio.open_memory_channel(1)


@pytest_trio.trio_fixture
async def bridged_channels(nursery,
                           endpoint,
                           remote_endpoint,
                           outgoing_packet_channels,
                           remote_outgoing_packet_channels,
                           incoming_packet_channels,
                           remote_incoming_packet_channels,
                           ):
    async def bridge_channels(outgoing_packet_receive_channel, incoming_packet_send_channel):
        async for outgoing_packet in outgoing_packet_receive_channel:
            receiver = outgoing_packet.receiver_endpoint
            sender = endpoint if receiver == remote_endpoint else remote_endpoint
            incoming_packet = IncomingPacket(
                packet=outgoing_packet.packet,
                sender_endpoint=sender,
            )
            await incoming_packet_send_channel.send(incoming_packet)

    nursery.start_soon(
        bridge_channels,
        outgoing_packet_channels[1],
        remote_incoming_packet_channels[0],
    )
    nursery.start_soon(
        bridge_channels,
        remote_outgoing_packet_channels[1],
        incoming_packet_channels[0],
    )


@pytest_trio.trio_fixture
async def peer_packer(enr_db,
                      private_key,
                      enr,
                      remote_enr,
                      incoming_packet_channels,
                      incoming_message_channels,
                      outgoing_message_channels,
                      outgoing_packet_channels):
    peer_packer = PeerPacker(
        local_private_key=private_key,
        local_node_id=enr.node_id,
        remote_node_id=remote_enr.node_id,
        enr_db=enr_db,
        message_type_registry=default_message_type_registry,
        incoming_packet_receive_channel=incoming_packet_channels[1],
        incoming_message_send_channel=incoming_message_channels[0],
        outgoing_message_receive_channel=outgoing_message_channels[1],
        outgoing_packet_send_channel=outgoing_packet_channels[0],
    )
    async with background_service(peer_packer):
        yield peer_packer


@pytest_trio.trio_fixture
async def remote_peer_packer(enr_db,
                             remote_private_key,
                             enr,
                             remote_enr,
                             remote_incoming_packet_channels,
                             remote_incoming_message_channels,
                             remote_outgoing_message_channels,
                             remote_outgoing_packet_channels):
    peer_packer = PeerPacker(
        local_private_key=remote_private_key,
        local_node_id=remote_enr.node_id,
        remote_node_id=enr.node_id,
        enr_db=enr_db,
        message_type_registry=default_message_type_registry,
        incoming_packet_receive_channel=remote_incoming_packet_channels[1],
        incoming_message_send_channel=remote_incoming_message_channels[0],
        outgoing_message_receive_channel=remote_outgoing_message_channels[1],
        outgoing_packet_send_channel=remote_outgoing_packet_channels[0],
    )
    async with background_service(peer_packer):
        yield peer_packer


@pytest_trio.trio_fixture
async def packer(enr_db,
                 private_key,
                 enr,
                 incoming_packet_channels,
                 incoming_message_channels,
                 outgoing_message_channels,
                 outgoing_packet_channels):
    packer = Packer(
        local_private_key=private_key,
        local_node_id=enr.node_id,
        enr_db=enr_db,
        message_type_registry=default_message_type_registry,
        incoming_packet_receive_channel=incoming_packet_channels[1],
        incoming_message_send_channel=incoming_message_channels[0],
        outgoing_message_receive_channel=outgoing_message_channels[1],
        outgoing_packet_send_channel=outgoing_packet_channels[0],
    )
    async with background_service(packer):
        yield packer


@pytest_trio.trio_fixture
async def remote_packer(enr_db,
                        remote_private_key,
                        remote_enr,
                        remote_incoming_packet_channels,
                        remote_incoming_message_channels,
                        remote_outgoing_message_channels,
                        remote_outgoing_packet_channels,
                        bridged_channels):
    remote_packer = Packer(
        local_private_key=remote_private_key,
        local_node_id=remote_enr.node_id,
        enr_db=enr_db,
        message_type_registry=default_message_type_registry,
        incoming_packet_receive_channel=remote_incoming_packet_channels[1],
        incoming_message_send_channel=remote_incoming_message_channels[0],
        outgoing_message_receive_channel=remote_outgoing_message_channels[1],
        outgoing_packet_send_channel=remote_outgoing_packet_channels[0],
    )
    async with background_service(remote_packer):
        yield packer


#
# Peer packer tests
#
@pytest.mark.trio
async def test_peer_packer_initiates_handshake(peer_packer,
                                               outgoing_message_channels,
                                               outgoing_packet_channels,
                                               nursery):
    outgoing_message = OutgoingMessage(
        PingMessageFactory(),
        EndpointFactory(),
        peer_packer.remote_node_id,
    )

    outgoing_message_channels[0].send_nowait(outgoing_message)
    with trio.fail_after(0.5):
        outgoing_packet = await outgoing_packet_channels[1].receive()

    assert peer_packer.is_during_handshake
    assert outgoing_packet.receiver_endpoint == outgoing_message.receiver_endpoint
    assert isinstance(outgoing_packet.packet, AuthTagPacket)


@pytest.mark.trio
async def test_peer_packer_sends_who_are_you(peer_packer,
                                             incoming_packet_channels,
                                             outgoing_packet_channels,
                                             nursery):
    incoming_packet = IncomingPacket(
        AuthTagPacketFactory(),
        EndpointFactory(),
    )

    incoming_packet_channels[0].send_nowait(incoming_packet)
    with trio.fail_after(0.5):
        outgoing_packet = await outgoing_packet_channels[1].receive()

    assert peer_packer.is_during_handshake
    assert outgoing_packet.receiver_endpoint == incoming_packet.sender_endpoint
    assert isinstance(outgoing_packet.packet, WhoAreYouPacket)
    assert outgoing_packet.packet.token == incoming_packet.packet.auth_tag


@pytest.mark.trio
async def test_peer_packer_sends_auth_header(peer_packer,
                                             enr,
                                             remote_enr,
                                             remote_endpoint,
                                             incoming_packet_channels,
                                             outgoing_packet_channels,
                                             outgoing_message_channels,
                                             nursery,
                                             ):
    outgoing_message = OutgoingMessage(
        PingMessageFactory(),
        remote_endpoint,
        peer_packer.remote_node_id,
    )
    outgoing_message_channels[0].send_nowait(outgoing_message)
    with trio.fail_after(0.5):
        outgoing_auth_tag_packet = await outgoing_packet_channels[1].receive()

    handshake_recipient = HandshakeRecipientFactory(
        local_private_key=remote_private_key,
        local_enr=remote_enr,
        remote_private_key=peer_packer.local_private_key,
        remote_enr=enr,
        remote_node_id=peer_packer.local_node_id,
        initiating_packet_auth_tag=outgoing_auth_tag_packet.packet.auth_tag,
    )
    incoming_packet = IncomingPacket(
        handshake_recipient.first_packet_to_send,
        sender_endpoint=remote_endpoint,
    )
    incoming_packet_channels[0].send_nowait(incoming_packet)
    with trio.fail_after(0.5):
        outgoing_auth_header_packet = await outgoing_packet_channels[1].receive()

    assert peer_packer.is_post_handshake
    assert isinstance(outgoing_auth_header_packet.packet, AuthHeaderPacket)
    assert outgoing_auth_header_packet.receiver_endpoint == remote_endpoint

    handshake_result = handshake_recipient.complete_handshake(
        outgoing_auth_header_packet.packet,
    )
    initiator_keys = peer_packer.session_keys
    recipient_keys = handshake_result.session_keys
    assert initiator_keys.auth_response_key == recipient_keys.auth_response_key
    assert initiator_keys.encryption_key == recipient_keys.decryption_key
    assert initiator_keys.decryption_key == recipient_keys.encryption_key


@pytest.mark.trio
async def test_full_peer_packer_handshake(peer_packer,
                                          remote_peer_packer,
                                          endpoint,
                                          remote_endpoint,
                                          enr,
                                          remote_enr,
                                          outgoing_message_channels,
                                          remote_outgoing_message_channels,
                                          incoming_message_channels,
                                          remote_incoming_message_channels,
                                          bridged_channels,
                                          nursery):
    # to remote
    outgoing_message = OutgoingMessage(
        message=PingMessageFactory(),
        receiver_endpoint=remote_endpoint,
        receiver_node_id=remote_enr.node_id,
    )
    outgoing_message_channels[0].send_nowait(outgoing_message)

    with trio.fail_after(0.5):
        incoming_message = await remote_incoming_message_channels[1].receive()

    assert incoming_message.message == outgoing_message.message
    assert incoming_message.sender_endpoint == endpoint
    assert incoming_message.sender_node_id == enr.node_id

    # from remote
    outgoing_message = OutgoingMessage(
        message=PingMessageFactory(),
        receiver_endpoint=endpoint,
        receiver_node_id=enr.node_id,
    )
    remote_outgoing_message_channels[0].send_nowait(outgoing_message)

    with trio.fail_after(0.5):
        incoming_message = await incoming_message_channels[1].receive()

    assert incoming_message.message == outgoing_message.message
    assert incoming_message.sender_endpoint == remote_endpoint
    assert incoming_message.sender_node_id == remote_enr.node_id


#
# Packer tests
#
@pytest.mark.trio
async def test_packer_sends_packets(nursery,
                                    packer,
                                    remote_enr,
                                    remote_endpoint,
                                    outgoing_message_channels,
                                    outgoing_packet_channels):
    assert not packer.is_peer_packer_registered(remote_enr.node_id)

    # send message
    outgoing_message = OutgoingMessage(
        message=PingMessageFactory(),
        receiver_endpoint=remote_endpoint,
        receiver_node_id=remote_enr.node_id,
    )
    outgoing_message_channels[0].send_nowait(outgoing_message)

    with trio.fail_after(0.5):
        outgoing_packet = await outgoing_packet_channels[1].receive()

    assert packer.is_peer_packer_registered(remote_enr.node_id)

    assert isinstance(outgoing_packet.packet, AuthTagPacket)
    assert outgoing_packet.receiver_endpoint == remote_endpoint


@pytest.mark.trio
async def test_packer_processes_handshake_initiation(nursery,
                                                     packer,
                                                     enr,
                                                     remote_enr,
                                                     remote_endpoint,
                                                     incoming_packet_channels):
    assert not packer.is_peer_packer_registered(remote_enr.node_id)

    # receive packet
    tag = compute_tag(source_node_id=remote_enr.node_id, destination_node_id=enr.node_id)
    incoming_packet = IncomingPacket(
        packet=AuthTagPacketFactory(tag=tag),
        sender_endpoint=remote_endpoint,
    )
    await incoming_packet_channels[0].send(incoming_packet)
    await trio.sleep(0)
    assert packer.is_peer_packer_registered(remote_enr.node_id)


@pytest.mark.trio
async def test_packer_full_handshake(nursery,
                                     packer,
                                     remote_packer,
                                     enr,
                                     remote_enr,
                                     endpoint,
                                     remote_endpoint,
                                     outgoing_message_channels,
                                     remote_outgoing_message_channels,
                                     incoming_message_channels,
                                     remote_incoming_message_channels):
    # to remote
    outgoing_message = OutgoingMessage(
        message=PingMessageFactory(),
        receiver_endpoint=remote_endpoint,
        receiver_node_id=remote_enr.node_id,
    )
    outgoing_message_channels[0].send_nowait(outgoing_message)

    with trio.fail_after(0.5):
        incoming_message = await remote_incoming_message_channels[1].receive()

    assert incoming_message.message == outgoing_message.message
    assert incoming_message.sender_endpoint == endpoint
    assert incoming_message.sender_node_id == enr.node_id

    # from remote
    outgoing_message = OutgoingMessage(
        message=PingMessageFactory(),
        receiver_endpoint=endpoint,
        receiver_node_id=enr.node_id,
    )
    remote_outgoing_message_channels[0].send_nowait(outgoing_message)

    with trio.fail_after(0.5):
        incoming_message = await incoming_message_channels[1].receive()

    assert incoming_message.message == outgoing_message.message
    assert incoming_message.sender_endpoint == remote_endpoint
    assert incoming_message.sender_node_id == remote_enr.node_id
