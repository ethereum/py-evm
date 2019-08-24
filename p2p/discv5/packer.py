import logging
from typing import (
    Dict,
    List,
    NamedTuple,
    Optional,
    Tuple,
)

from eth_utils import (
    encode_hex,
    ValidationError,
)

import trio
from trio.abc import (
    ReceiveChannel,
    SendChannel,
)

from p2p.trio_service import (
    LifecycleError,
    Service,
    Manager,
)

from p2p.discv5.abc import (
    EnrDbApi,
    HandshakeParticipantAPI,
)
from p2p.discv5.channel_services import (
    Endpoint,
    IncomingMessage,
    IncomingPacket,
    OutgoingMessage,
    OutgoingPacket,
)
from p2p.discv5.enr import (
    ENR,
)
from p2p.discv5.handshake import (
    HandshakeInitiator,
    HandshakeRecipient,
)
from p2p.discv5.messages import (
    BaseMessage,
    MessageTypeRegistry,
)
from p2p.discv5.packets import (
    AuthTagPacket,
    get_random_auth_tag,
)
from p2p.discv5.tags import (
    compute_tag,
    recover_source_id_from_tag,
)
from p2p.discv5.typing import (
    NodeID,
    Nonce,
    SessionKeys,
)

from p2p.exceptions import (
    DecryptionError,
    HandshakeFailure,
)


class PeerPacker(Service):
    handshake_participant: Optional[HandshakeParticipantAPI] = None
    session_keys: Optional[SessionKeys] = None

    def __init__(self,
                 local_private_key: bytes,
                 local_node_id: NodeID,
                 remote_node_id: NodeID,
                 enr_db: EnrDbApi,
                 message_type_registry: MessageTypeRegistry,
                 incoming_packet_receive_channel: ReceiveChannel[IncomingPacket],
                 incoming_message_send_channel: SendChannel[IncomingMessage],
                 outgoing_message_receive_channel: ReceiveChannel[OutgoingMessage],
                 outgoing_packet_send_channel: SendChannel[OutgoingPacket],
                 ) -> None:
        self.local_private_key = local_private_key
        self.local_node_id = local_node_id
        self.remote_node_id = remote_node_id
        self.enr_db = enr_db
        self.message_type_registry = message_type_registry

        self.incoming_packet_receive_channel = incoming_packet_receive_channel
        self.incoming_message_send_channel = incoming_message_send_channel
        self.outgoing_message_receive_channel = outgoing_message_receive_channel
        self.outgoing_packet_send_channel = outgoing_packet_send_channel

        self.logger = logging.getLogger(
            f"p2p.discv5.packer.PeerPacker[{encode_hex(remote_node_id)[2:10]}]"
        )

        self.outgoing_message_backlog: List[OutgoingMessage] = []

    def __str__(self) -> str:
        return f"{self.__class__.__name__}[{encode_hex(self.remote_node_id)[2:10]}]"

    async def run(self) -> None:
        async with self.incoming_packet_receive_channel, self.incoming_message_send_channel,  \
                self.outgoing_message_receive_channel, self.outgoing_packet_send_channel:
            self.manager.run_daemon_task(self.handle_incoming_packets)
            self.manager.run_daemon_task(self.handle_outgoing_messages)
            await self.manager.wait_stopped()

    async def handle_incoming_packets(self) -> None:
        async for incoming_packet in self.incoming_packet_receive_channel:
            # Handle packets sequentially, so that the rest of the code doesn't have to deal
            # with multiple packets being processed at the same time.
            await self.handle_incoming_packet(incoming_packet)

    async def handle_incoming_packet(self, incoming_packet: IncomingPacket) -> None:
        if self.is_pre_handshake:
            await self.handle_incoming_packet_pre_handshake(incoming_packet)
        elif self.is_during_handshake:
            await self.handle_incoming_packet_during_handshake(incoming_packet)
        elif self.is_post_handshake:
            await self.handle_incoming_packet_post_handshake(incoming_packet)
        else:
            raise Exception("Invariant: All states handled")

    async def handle_outgoing_messages(self) -> None:
        async for outgoing_message in self.outgoing_message_receive_channel:
            # Similar to the incoming packets outgoing messages are processed in sequence, even
            # though it's not that critical here
            await self.handle_outgoing_message(outgoing_message)

    async def handle_outgoing_message(self, outgoing_message: OutgoingMessage) -> None:
        if self.is_pre_handshake:
            await self.handle_outgoing_message_pre_handshake(outgoing_message)
        elif self.is_during_handshake:
            await self.handle_outgoing_message_during_handshake(outgoing_message)
        elif self.is_post_handshake:
            await self.handle_outgoing_message_post_handshake(outgoing_message)
        else:
            raise Exception("Invariant: All states handled")

    #
    # Incoming packet handlers
    #
    async def handle_incoming_packet_pre_handshake(self, incoming_packet: IncomingPacket) -> None:
        if not self.is_pre_handshake:
            raise ValueError("Can only handle packets pre handshake")

        if isinstance(incoming_packet.packet, AuthTagPacket):
            try:
                remote_enr = await self.enr_db.get(self.remote_node_id)
            except KeyError:
                remote_enr = None
            try:
                local_enr = await self.enr_db.get(self.local_node_id)
            except KeyError:
                raise ValueError(
                    f"Unable to find local ENR in DB by node id {encode_hex(self.local_node_id)}"
                )

            # There's a minimal chance that while we were looking up the ENRs in the db, we've
            # initiated a handshake ourselves. Therefore, we check that we are still in the pre
            # handshake state, if not we just drop the packet (which is what we always do with
            # AuthTag packets received after we have initiated a handshake).
            if self.is_pre_handshake:
                self.logger.debug("Received %s as handshake initiation", incoming_packet)
                self.start_handshake_as_recipient(
                    auth_tag=incoming_packet.packet.auth_tag,
                    local_enr=local_enr,
                    remote_enr=remote_enr,
                )
            else:
                self.logger.warning(
                    "Dropping %s previously thought to initiate handshake as we have initiated "
                    "handshake ourselves in the meantime",
                    incoming_packet,
                )

            self.logger.debug("Responding with WhoAreYou packet")
            await self.send_first_handshake_packet(incoming_packet.sender_endpoint)
        else:
            self.logger.debug("Dropping %s as handshake has not been started yet", incoming_packet)

    async def handle_incoming_packet_during_handshake(self,
                                                      incoming_packet: IncomingPacket,
                                                      ) -> None:
        if not self.is_during_handshake:
            raise ValueError("Can only handle packets during handshake")
        if self.handshake_participant is None:
            raise TypeError("handshake_participant is None even though handshake is in progress")

        packet = incoming_packet.packet

        if self.handshake_participant.is_response_packet(packet):
            self.logger.debug("Received %s as handshake response", packet.__class__.__name__)
        else:
            self.logger.debug("Dropping %s unexpectedly received during handshake", incoming_packet)
            return

        try:
            handshake_result = self.handshake_participant.complete_handshake(packet)
        except HandshakeFailure as handshake_failure:
            self.logger.warning(
                "Handshake with %s has failed: %s",
                encode_hex(self.remote_node_id),
                handshake_failure,
            )
            raise  # let the service fail
        else:
            self.logger.info("Handshake with %s was successful", encode_hex(self.remote_node_id))

            # copy message backlog before we reset it
            outgoing_message_backlog = tuple(self.outgoing_message_backlog)
            self.reset_handshake_state()
            self.session_keys = handshake_result.session_keys
            if not self.is_post_handshake:
                raise Exception(
                    "Invariant: As session_keys are set now, peer packer is in post handshake state"
                )

            if handshake_result.enr is not None:
                self.logger.debug("Updating ENR in DB with %r", handshake_result.enr)
                await self.enr_db.insert_or_update(handshake_result.enr)

            if handshake_result.auth_header_packet is not None:
                outgoing_packet = OutgoingPacket(
                    handshake_result.auth_header_packet,
                    incoming_packet.sender_endpoint,
                )
                self.logger.debug(
                    "Sending %s packet to let peer complete handshake",
                    outgoing_packet,
                )
                await self.outgoing_packet_send_channel.send(outgoing_packet)

            if handshake_result.message:
                incoming_message = IncomingMessage(
                    handshake_result.message,
                    incoming_packet.sender_endpoint,
                    self.remote_node_id,
                )
                self.logger.debug("Received %s during handshake", incoming_message)
                await self.incoming_message_send_channel.send(incoming_message)

            self.logger.debug("Sending %d messages from backlog", len(outgoing_message_backlog))
            for outgoing_message in outgoing_message_backlog:
                await self.handle_outgoing_message(outgoing_message)

    async def handle_incoming_packet_post_handshake(self, incoming_packet: IncomingPacket) -> None:
        if not self.is_post_handshake:
            raise ValueError("Can only handle packets post handshake")
        if self.session_keys is None:
            raise TypeError("session_keys are None even though handshake has been completed")

        if isinstance(incoming_packet.packet, AuthTagPacket):
            try:
                message = incoming_packet.packet.decrypt_message(
                    self.session_keys.decryption_key,
                    self.message_type_registry,
                )
            except DecryptionError:
                self.logger.info(
                    "Failed to decrypt message from peer, starting another handshake as recipient"
                )
                self.reset_handshake_state()
                await self.handle_incoming_packet_pre_handshake(incoming_packet)
            except ValidationError as validation_error:
                self.logger.warning("Received invalid packet: %s", validation_error)
                raise  # let the service fail
            else:
                incoming_message = IncomingMessage(
                    message,
                    incoming_packet.sender_endpoint,
                    self.remote_node_id,
                )
                self.logger.debug("Received %s", incoming_message)
                await self.incoming_message_send_channel.send(incoming_message)
        else:
            self.logger.debug(
                "Dropping %s as handshake has already been completed",
                incoming_packet,
            )

    #
    # Outgoing message handlers
    #
    async def handle_outgoing_message_pre_handshake(self,
                                                    outgoing_message: OutgoingMessage,
                                                    ) -> None:
        if not self.is_pre_handshake:
            raise ValueError("Can only handle message pre handshake")

        try:
            local_enr = await self.enr_db.get(self.local_node_id)
        except KeyError:
            raise ValueError(
                f"Unable to find local ENR in DB by node id {encode_hex(self.local_node_id)}"
            )
        try:
            remote_enr = await self.enr_db.get(self.remote_node_id)
        except KeyError:
            self.logger.warning(
                "Unable to initiate handshake with %s as their ENR is not present in the DB",
                encode_hex(self.remote_node_id),
            )
            raise HandshakeFailure()

        # There is a minimal chance that while we were looking up the ENRs in the db, the peer has
        # initiated a handshake by themselves. Therefore, we check that we are still in the pre
        # handshake state, if not we just handle the packet again (which will most likely result in
        # the message being put on the backlog).
        if self.is_pre_handshake:
            self.logger.info("Initiating handshake to send %s", outgoing_message)
            self.start_handshake_as_initiator(
                local_enr=local_enr,
                remote_enr=remote_enr,
                message=outgoing_message.message,
            )
            self.logger.debug("Sending initiating packet")
            await self.send_first_handshake_packet(outgoing_message.receiver_endpoint)
        else:
            await self.handle_outgoing_message(outgoing_message)

    async def handle_outgoing_message_during_handshake(self,
                                                       outgoing_message: OutgoingMessage
                                                       ) -> None:
        if not self.is_during_handshake:
            raise ValueError("Can only handle message during handshake")

        self.logger.debug(
            "Putting %s on message backlog as handshake is in progress already",
            outgoing_message,
        )
        self.outgoing_message_backlog.append(outgoing_message)
        await trio.sleep(0)

    async def handle_outgoing_message_post_handshake(self,
                                                     outgoing_message: OutgoingMessage,
                                                     ) -> None:
        if not self.is_post_handshake:
            raise ValueError("Can only handle message post handshake")
        if self.session_keys is None:
            raise TypeError("session_keys are None even though handshake has been completed")

        packet = AuthTagPacket.prepare(
            tag=compute_tag(self.local_node_id, self.remote_node_id),
            auth_tag=get_random_auth_tag(),
            message=outgoing_message.message,
            key=self.session_keys.encryption_key,
        )
        outgoing_packet = OutgoingPacket(
            packet,
            outgoing_message.receiver_endpoint,
        )
        self.logger.debug("Sending %s", outgoing_message)
        await self.outgoing_packet_send_channel.send(outgoing_packet)

    #
    # Start Handshake Methods
    #
    def start_handshake_as_initiator(self,
                                     local_enr: ENR,
                                     remote_enr: ENR,
                                     message: BaseMessage,
                                     ) -> None:
        if not self.is_pre_handshake:
            raise ValueError("Can only register handshake when its not started yet")

        self.handshake_participant = HandshakeInitiator(
            local_private_key=self.local_private_key,
            local_enr=local_enr,
            remote_enr=remote_enr,
            initial_message=message,
        )

        if not self.is_during_handshake:
            raise Exception("Invariant: After a handshake is started, the handshake is in progress")

    def start_handshake_as_recipient(self,
                                     auth_tag: Nonce,
                                     local_enr: ENR,
                                     remote_enr: Optional[ENR],
                                     ) -> None:
        if not self.is_pre_handshake:
            raise ValueError("Can only register handshake when its not started yet")

        self.handshake_participant = HandshakeRecipient(
            local_private_key=self.local_private_key,
            local_enr=local_enr,
            remote_node_id=self.remote_node_id,
            remote_enr=remote_enr,
            initiating_packet_auth_tag=auth_tag,
        )

        if not self.is_during_handshake:
            raise Exception("Invariant: After a handshake is started, the handshake is in progress")

    #
    # Handshake states
    #
    @property
    def is_pre_handshake(self) -> bool:
        """True if neither session keys are available nor a handshake is in progress."""
        return self.handshake_participant is None and self.session_keys is None

    @property
    def is_during_handshake(self) -> bool:
        """True if a handshake is in progress, but not completed yet."""
        return self.handshake_participant is not None

    @property
    def is_post_handshake(self) -> bool:
        """True if session keys from a preceding handshake are available."""
        return self.handshake_participant is None and self.session_keys is not None

    def reset_handshake_state(self) -> None:
        """Return to the pre handshake state.

        This deletes the session keys, the handshake participant instance, and all messages on the
        message backlog. After this method is called, a new handshake can be initiated.
        """
        if self.is_pre_handshake:
            raise ValueError("Handshake is already in pre state")
        self.handshake_participant = None
        self.session_keys = None
        self.outgoing_message_backlog.clear()

    def is_expecting_handshake_packet(self, incoming_packet: IncomingPacket) -> bool:
        """Check if the peer packer is waiting for the given packet to complete a handshake.

        This should be called before putting the packet in question on the peer's incoming packet
        channel.
        """
        return (
            self.is_during_handshake and
            self.handshake_participant.is_response_packet(incoming_packet.packet)
        )

    async def send_first_handshake_packet(self, receiver_endpoint: Endpoint) -> None:
        outgoing_packet = OutgoingPacket(
            self.handshake_participant.first_packet_to_send,
            receiver_endpoint,
        )
        await self.outgoing_packet_send_channel.send(outgoing_packet)


class ManagedPeerPacker(NamedTuple):
    peer_packer: PeerPacker
    manager: Manager
    incoming_packet_send_channel: SendChannel[IncomingPacket]
    outgoing_message_send_channel: SendChannel[OutgoingMessage]


class Packer(Service):

    def __init__(self,
                 local_private_key: bytes,
                 local_node_id: NodeID,
                 enr_db: EnrDbApi,
                 message_type_registry: MessageTypeRegistry,
                 incoming_packet_receive_channel: ReceiveChannel[IncomingPacket],
                 incoming_message_send_channel: SendChannel[IncomingMessage],
                 outgoing_message_receive_channel: ReceiveChannel[OutgoingMessage],
                 outgoing_packet_send_channel: SendChannel[OutgoingPacket],
                 ) -> None:
        self.local_private_key = local_private_key
        self.local_node_id = local_node_id
        self.enr_db = enr_db
        self.message_type_registry = message_type_registry

        self.incoming_packet_receive_channel = incoming_packet_receive_channel
        self.incoming_message_send_channel = incoming_message_send_channel
        self.outgoing_message_receive_channel = outgoing_message_receive_channel
        self.outgoing_packet_send_channel = outgoing_packet_send_channel

        self.logger = logging.getLogger("p2p.discv5.packer.Packer")

        self.managed_peer_packers: Dict[NodeID, ManagedPeerPacker] = {}

    async def run(self) -> None:
        self.manager.run_daemon_task(self.handle_incoming_packets)
        self.manager.run_daemon_task(self.handle_outgoing_messages)
        await self.manager.wait_stopped()

    async def handle_incoming_packets(self) -> None:
        async for incoming_packet in self.incoming_packet_receive_channel:
            expecting_managed_peer_packers = tuple(
                managed_peer_packer
                for managed_peer_packer in self.managed_peer_packers.values()
                if managed_peer_packer.peer_packer.is_expecting_handshake_packet(incoming_packet)
            )
            if len(expecting_managed_peer_packers) >= 2:
                self.logger.warning(
                    "Multiple peer packers are expecting %s: %s",
                    incoming_packet,
                    ", ".join(
                        encode_hex(managed_peer_packer.peer_packer.local_node_id)
                        for managed_peer_packer in expecting_managed_peer_packers
                    ),
                )

            if expecting_managed_peer_packers:
                for managed_peer_packer in expecting_managed_peer_packers:
                    self.logger.debug(
                        "Passing %s to %s for handshake",
                        incoming_packet,
                        managed_peer_packer.peer_packer,
                    )
                    await managed_peer_packer.incoming_packet_send_channel.send(incoming_packet)

            elif isinstance(incoming_packet.packet, AuthTagPacket):
                tag = incoming_packet.packet.tag
                remote_node_id = recover_source_id_from_tag(tag, self.local_node_id)

                if not self.is_peer_packer_registered(remote_node_id):
                    self.logger.info(
                        "Launching peer packer for %s to handle %s",
                        encode_hex(remote_node_id),
                        incoming_packet,
                    )
                    self.register_peer_packer(remote_node_id)
                    self.manager.run_task(self.run_peer_packer, remote_node_id)

                managed_peer_packer = self.managed_peer_packers[remote_node_id]
                self.logger.debug(
                    "Passing %s from %s to responsible peer packer",
                    incoming_packet,
                    encode_hex(remote_node_id),
                )
                await managed_peer_packer.incoming_packet_send_channel.send(incoming_packet)

            else:
                self.logger.warning("Dropping unprompted handshake packet %s", incoming_packet)

    async def handle_outgoing_messages(self) -> None:
        async for outgoing_message in self.outgoing_message_receive_channel:
            remote_node_id = outgoing_message.receiver_node_id
            if not self.is_peer_packer_registered(remote_node_id):
                self.logger.info(
                    "Launching peer packer for %s to handle %s",
                    encode_hex(remote_node_id),
                    outgoing_message,
                )
                self.register_peer_packer(remote_node_id)
                self.manager.run_task(self.run_peer_packer, remote_node_id)

            self.logger.debug(
                "Passing %s from %s to responsible peer packer",
                outgoing_message,
                encode_hex(remote_node_id),
            )
            managed_peer_packer = self.managed_peer_packers[remote_node_id]
            await managed_peer_packer.outgoing_message_send_channel.send(outgoing_message)

    #
    # Peer packer handling
    #
    def is_peer_packer_registered(self, remote_node_id: NodeID) -> bool:
        return remote_node_id in self.managed_peer_packers

    def register_peer_packer(self, remote_node_id: NodeID) -> None:
        if self.is_peer_packer_registered(remote_node_id):
            raise ValueError(f"Peer packer for {encode_hex(remote_node_id)} is already registered")

        incoming_packet_channels: Tuple[
            SendChannel[IncomingPacket],
            ReceiveChannel[IncomingPacket],
        ] = trio.open_memory_channel(0)
        outgoing_message_channels: Tuple[
            SendChannel[OutgoingMessage],
            ReceiveChannel[OutgoingMessage],
        ] = trio.open_memory_channel(0)

        peer_packer = PeerPacker(
            local_private_key=self.local_private_key,
            local_node_id=self.local_node_id,
            remote_node_id=remote_node_id,
            enr_db=self.enr_db,
            message_type_registry=self.message_type_registry,
            incoming_packet_receive_channel=incoming_packet_channels[1],
            incoming_message_send_channel=self.incoming_message_send_channel,
            outgoing_message_receive_channel=outgoing_message_channels[1],
            outgoing_packet_send_channel=self.outgoing_packet_send_channel,
        )

        manager = Manager(peer_packer)

        self.managed_peer_packers[remote_node_id] = ManagedPeerPacker(
            peer_packer=peer_packer,
            manager=manager,
            incoming_packet_send_channel=incoming_packet_channels[0],
            outgoing_message_send_channel=outgoing_message_channels[0],
        )

    def deregister_peer_packer(self, remote_node_id: NodeID) -> None:
        if not self.is_peer_packer_registered(remote_node_id):
            raise ValueError(f"Peer packer for {encode_hex(remote_node_id)} is not registered")
        managed_peer_packer = self.managed_peer_packers[remote_node_id]
        if managed_peer_packer.manager.is_running:
            raise ValueError(
                f"Peer packer for {encode_hex(remote_node_id)} is still running"
            )

        self.managed_peer_packers.pop(remote_node_id)

    async def run_peer_packer(self, remote_node_id: NodeID) -> None:
        if not self.is_peer_packer_registered(remote_node_id):
            raise ValueError("Peer packer for {encode_hex(remote_node_id)} is not registered")
        managed_peer_packer = self.managed_peer_packers[remote_node_id]

        try:
            await managed_peer_packer.manager.run()
        except LifecycleError as lifecycle_error:
            raise ValueError(
                "Peer packer for {encode_hex(remote_node_id)} has already been started"
            ) from lifecycle_error
        except HandshakeFailure as handshake_failure:
            # peer packer has logged a warning already
            self.logger.debug(
                "Peer packer %s has failed to do handshake with %s",
                managed_peer_packer.peer_packer,
                handshake_failure,
            )
        finally:
            self.logger.info("Deregistering peer packer %s", managed_peer_packer.peer_packer)
            self.deregister_peer_packer(remote_node_id)
