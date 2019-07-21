import logging
from typing import (
    NamedTuple,
)

from trio.socket import (
    SocketType,
)
from trio.abc import (
    ReceiveChannel,
    SendChannel,
)

from p2p.trio_service import (
    as_service,
    Manager,
)

from p2p.discv5.constants import (
    DATAGRAM_BUFFER_SIZE,
)


class Endpoint(NamedTuple):
    ip_address: bytes
    port: int


class IncomingDatagram(NamedTuple):
    datagram: bytes
    sender: Endpoint


class OutgoingDatagram(NamedTuple):
    datagram: bytes
    receiver: Endpoint


@as_service
async def DatagramReceiver(manager: Manager,
                           socket: SocketType,
                           incoming_datagram_send_channel: SendChannel[IncomingDatagram],
                           ) -> None:
    """Read datagrams from a socket and send them to a channel."""
    logger = logging.getLogger('p2p.discv5.channel_services.DatagramReceiver')

    async with incoming_datagram_send_channel:
        while manager.is_running:
            datagram, (ip_address, port) = await socket.recvfrom(DATAGRAM_BUFFER_SIZE)
            logger.debug(f"Received {len(datagram)} bytes from {(ip_address, port)}")
            incoming_datagram = IncomingDatagram(datagram, Endpoint(ip_address, port))
            await incoming_datagram_send_channel.send(incoming_datagram)


@as_service
async def DatagramSender(manager: Manager,
                         outgoing_datagram_receive_channel: ReceiveChannel[OutgoingDatagram],
                         socket: SocketType,
                         ) -> None:
    """Take datagrams from a channel and send them via a socket to their designated receivers."""
    logger = logging.getLogger('p2p.discv5.channel_services.DatagramSender')

    async with outgoing_datagram_receive_channel:
        async for datagram, (ip_address, port) in outgoing_datagram_receive_channel:
            logger.debug(f"Sending {len(datagram)} bytes to {(ip_address, port)}")
            await socket.sendto(datagram, (ip_address, port))
