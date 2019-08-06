import trio

import pytest
import pytest_trio

from p2p.trio_service import (
    background_service,
)

from p2p.discv5.channel_services import (
    DatagramReceiver,
    DatagramSender,
    OutgoingDatagram,
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
        assert received_datagram.sender.ip_address == sender_address[0]
        assert received_datagram.sender.port == sender_address[1]


@pytest.mark.trio
async def test_datagram_sender(socket_pair):
    sending_socket, receiving_socket = socket_pair
    receiver_address = receiving_socket.getsockname()
    sender_address = sending_socket.getsockname()

    send_channel, receive_channel = trio.open_memory_channel(1)
    async with background_service(DatagramSender(receive_channel, sending_socket)):
        outgoing_datagram = OutgoingDatagram(b"some packet", receiver_address)
        await send_channel.send(outgoing_datagram)

        with trio.fail_after(0.5):
            data, sender = await receiving_socket.recvfrom(1024)
        assert data == outgoing_datagram.datagram
        assert sender == sender_address
