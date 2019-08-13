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

from eth_utils import (
    ValidationError,
)

from p2p.trio_service import (
    as_service,
    ManagerAPI,
)

from p2p.discv5.packets import (
    decode_packet,
    Packet,
)
from p2p.discv5.constants import (
    DATAGRAM_BUFFER_SIZE,
)


#
# Data structures
#
class Endpoint(NamedTuple):
    ip_address: str
    port: int


class IncomingDatagram(NamedTuple):
    datagram: bytes
    sender_endpoint: Endpoint


class OutgoingDatagram(NamedTuple):
    datagram: bytes
    receiver_endpoint: Endpoint


class IncomingPacket(NamedTuple):
    packet: Packet
    sender_endpoint: Endpoint


class OutgoingPacket(NamedTuple):
    packet: Packet
    receiver_endpoint: Endpoint


#
# UDP
#
@as_service
async def DatagramReceiver(manager: ManagerAPI,
                           socket: SocketType,
                           incoming_datagram_send_channel: SendChannel[IncomingDatagram],
                           ) -> None:
    """Read datagrams from a socket and send them to a channel."""
    logger = logging.getLogger('p2p.discv5.channel_services.DatagramReceiver')

    async with incoming_datagram_send_channel:
        while manager.is_running:
            datagram, (ip_address, port) = await socket.recvfrom(DATAGRAM_BUFFER_SIZE)
            endpoint = Endpoint(ip_address, port)
            logger.debug(f"Received {len(datagram)} bytes from {endpoint}")
            incoming_datagram = IncomingDatagram(datagram, endpoint)
            await incoming_datagram_send_channel.send(incoming_datagram)


@as_service
async def DatagramSender(manager: ManagerAPI,
                         outgoing_datagram_receive_channel: ReceiveChannel[OutgoingDatagram],
                         socket: SocketType,
                         ) -> None:
    """Take datagrams from a channel and send them via a socket to their designated receivers."""
    logger = logging.getLogger('p2p.discv5.channel_services.DatagramSender')

    async with outgoing_datagram_receive_channel:
        async for datagram, endpoint in outgoing_datagram_receive_channel:
            logger.debug(f"Sending {len(datagram)} bytes to {endpoint}")
            await socket.sendto(datagram, endpoint)


#
# Packet encoding/decoding
#
@as_service
async def PacketDecoder(manager: ManagerAPI,
                        incoming_datagram_receive_channel: ReceiveChannel[IncomingDatagram],
                        incoming_packet_send_channel: SendChannel[IncomingPacket],
                        ) -> None:
    """Decodes incoming datagrams to packet objects."""
    logger = logging.getLogger('p2p.discv5.channel_services.PacketDecoder')

    async with incoming_datagram_receive_channel, incoming_packet_send_channel:
        async for datagram, endpoint in incoming_datagram_receive_channel:
            try:
                packet = decode_packet(datagram)
                logger.debug(
                    f"Successfully decoded {packet.__class__.__name__} from {endpoint}"
                )
            except ValidationError:
                logger.warn(f"Failed to decode a packet from {endpoint}", exc_info=True)
            else:
                await incoming_packet_send_channel.send(IncomingPacket(packet, endpoint))


@as_service
async def PacketEncoder(manager: ManagerAPI,
                        outgoing_packet_receive_channel: ReceiveChannel[OutgoingPacket],
                        outgoing_datagram_send_channel: SendChannel[OutgoingDatagram],
                        ) -> None:
    """Encodes outgoing packets to datagrams."""
    logger = logging.getLogger('p2p.discv5.channel_services.PacketEncoder')

    async with outgoing_packet_receive_channel, outgoing_datagram_send_channel:
        async for packet, endpoint in outgoing_packet_receive_channel:
            outgoing_datagram = OutgoingDatagram(packet.to_wire_bytes(), endpoint)
            logger.debug(
                f"Encoded {packet.__class__.__name__} for {endpoint}"
            )
            await outgoing_datagram_send_channel.send(outgoing_datagram)
