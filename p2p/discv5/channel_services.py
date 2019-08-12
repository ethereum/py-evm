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
    ip_address: bytes
    port: int


class IncomingDatagram(NamedTuple):
    datagram: bytes
    sender: Endpoint


class OutgoingDatagram(NamedTuple):
    datagram: bytes
    receiver: Endpoint


class IncomingPacket(NamedTuple):
    packet: Packet
    sender: Endpoint


class OutgoingPacket(NamedTuple):
    packet: Packet
    receiver: Endpoint


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
            logger.debug(f"Received {len(datagram)} bytes from {(ip_address, port)}")
            incoming_datagram = IncomingDatagram(datagram, Endpoint(ip_address, port))
            await incoming_datagram_send_channel.send(incoming_datagram)


@as_service
async def DatagramSender(manager: ManagerAPI,
                         outgoing_datagram_receive_channel: ReceiveChannel[OutgoingDatagram],
                         socket: SocketType,
                         ) -> None:
    """Take datagrams from a channel and send them via a socket to their designated receivers."""
    logger = logging.getLogger('p2p.discv5.channel_services.DatagramSender')

    async with outgoing_datagram_receive_channel:
        async for datagram, (ip_address, port) in outgoing_datagram_receive_channel:
            logger.debug(f"Sending {len(datagram)} bytes to {(ip_address, port)}")
            await socket.sendto(datagram, (ip_address, port))


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
        async for datagram, sender in incoming_datagram_receive_channel:
            try:
                packet = decode_packet(datagram)
                logger.debug(
                    f"Successfully decoded {packet.__class__.__name__} from {sender}"
                )
            except ValidationError:
                logger.warn(f"Failed to decode a packet from {sender}", exc_info=True)
            else:
                await incoming_packet_send_channel.send(IncomingPacket(packet, sender))


@as_service
async def PacketEncoder(manager: ManagerAPI,
                        outgoing_packet_receive_channel: ReceiveChannel[OutgoingPacket],
                        outgoing_datagram_send_channel: SendChannel[OutgoingDatagram],
                        ) -> None:
    """Encodes outgoing packets to datagrams."""
    logger = logging.getLogger('p2p.discv5.channel_services.PacketEncoder')

    async with outgoing_packet_receive_channel, outgoing_datagram_send_channel:
        async for packet, receiver in outgoing_packet_receive_channel:
            outgoing_datagram = OutgoingDatagram(packet.to_wire_bytes(), receiver)
            logger.debug(
                f"Encoded {packet.__class__.__name__} for {receiver}"
            )
            await outgoing_datagram_send_channel.send(outgoing_datagram)
