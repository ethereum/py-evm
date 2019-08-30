import trio
from socket import (
    inet_aton,
)

import pytest
import pytest_trio

from p2p.trio_service import (
    background_service,
)

from p2p.discv5.channel_services import (
    DatagramReceiver,
    DatagramSender,
    Endpoint,
    IncomingDatagram,
    OutgoingDatagram,
    OutgoingPacket,
    PacketDecoder,
    PacketEncoder,
)

from p2p.tools.factories import (
    AuthTagPacketFactory,
    EndpointFactory,
)


@pytest_trio.trio_fixture
async def socket_pair():
    sending_socket = trio.socket.socket(
        family=trio.socket.AF_INET,
        type=trio.socket.SOCK_DGRAM,
    )
    receiving_socket = trio.socket.socket(
        family=trio.socket.AF_INET,
        type=trio.socket.SOCK_DGRAM,
    )
    # specifying 0 as port number results in using random available port
    await sending_socket.bind(("127.0.0.1", 0))
    await receiving_socket.bind(("127.0.0.1", 0))
    return sending_socket, receiving_socket


@pytest.mark.trio
async def test_datagram_receiver(socket_pair):
    sending_socket, receiving_socket = socket_pair
    receiver_address = receiving_socket.getsockname()
    sender_address = sending_socket.getsockname()

    send_channel, receive_channel = trio.open_memory_channel(1)
    async with background_service(DatagramReceiver(receiving_socket, send_channel)):
        data = b"some packet"

        await sending_socket.sendto(data, receiver_address)
        with trio.fail_after(0.5):
            received_datagram = await receive_channel.receive()

        assert received_datagram.datagram == data
        assert received_datagram.sender_endpoint.ip_address == inet_aton(sender_address[0])
        assert received_datagram.sender_endpoint.port == sender_address[1]


@pytest.mark.trio
async def test_datagram_sender(socket_pair):
    sending_socket, receiving_socket = socket_pair
    receiver_endpoint = receiving_socket.getsockname()
    sender_endpoint = sending_socket.getsockname()

    send_channel, receive_channel = trio.open_memory_channel(1)
    async with background_service(DatagramSender(receive_channel, sending_socket)):
        outgoing_datagram = OutgoingDatagram(
            b"some packet",
            Endpoint(inet_aton(receiver_endpoint[0]), receiver_endpoint[1]),
        )
        await send_channel.send(outgoing_datagram)

        with trio.fail_after(0.5):
            data, sender = await receiving_socket.recvfrom(1024)
        assert data == outgoing_datagram.datagram
        assert sender == sender_endpoint


async def test_packet_decoder():
    datagram_send_channel, datagram_receive_channel = trio.open_memory_channel(1)
    packet_send_channel, packet_receive_channel = trio.open_memory_channel(1)

    async with background_service(PacketDecoder(datagram_receive_channel, packet_send_channel)):
        packet = AuthTagPacketFactory()
        sender_endpoint = EndpointFactory()
        await datagram_send_channel.send(IncomingDatagram(
            datagram=packet.to_wire_bytes(),
            sender_endpoint=sender_endpoint,
        ))

        with trio.fail_after(0.5):
            incoming_packet = await packet_receive_channel.receive()

        assert incoming_packet.packet == packet
        assert incoming_packet.sender_endpoint.ip_address == sender_endpoint.ip_address
        assert incoming_packet.sender_endpoint.port == sender_endpoint.port


async def test_packet_decoder_error():
    datagram_send_channel, datagram_receive_channel = trio.open_memory_channel(1)
    packet_send_channel, packet_receive_channel = trio.open_memory_channel(1)

    async with background_service(PacketDecoder(datagram_receive_channel, packet_send_channel)):
        # send invalid packet
        await datagram_send_channel.send(IncomingDatagram(
            datagram=b"not a valid packet",
            sender_endpoint=EndpointFactory(),
        ))

        # send valid packet
        packet = AuthTagPacketFactory()
        sender_endpoint = EndpointFactory()
        await datagram_send_channel.send(IncomingDatagram(
            datagram=packet.to_wire_bytes(),
            sender_endpoint=sender_endpoint,
        ))

        # ignore the invalid one, only receive the valid one
        with trio.fail_after(0.5):
            incoming_packet = await packet_receive_channel.receive()

        assert incoming_packet.packet == packet
        assert incoming_packet.sender_endpoint.ip_address == sender_endpoint.ip_address
        assert incoming_packet.sender_endpoint.port == sender_endpoint.port


async def test_packet_encoder():
    packet_send_channel, packet_receive_channel = trio.open_memory_channel(1)
    datagram_send_channel, datagram_receive_channel = trio.open_memory_channel(1)

    async with background_service(PacketEncoder(packet_receive_channel, datagram_send_channel)):
        receiver_endpoint = EndpointFactory()
        outgoing_packet = OutgoingPacket(
            packet=AuthTagPacketFactory(),
            receiver_endpoint=receiver_endpoint,
        )
        await packet_send_channel.send(outgoing_packet)

        with trio.fail_after(0.5):
            outgoing_datagram = await datagram_receive_channel.receive()

        assert outgoing_datagram.datagram == outgoing_packet.packet.to_wire_bytes()
        assert outgoing_datagram.receiver_endpoint.ip_address == receiver_endpoint.ip_address
        assert outgoing_datagram.receiver_endpoint.port == receiver_endpoint.port
