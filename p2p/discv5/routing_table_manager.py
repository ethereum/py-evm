import logging
import time

from eth_utils import (
    encode_hex,
)

import trio
from trio.abc import (
    SendChannel,
)

from mypy_extensions import (
    TypedDict,
)

from async_service import (
    Service,
)
from p2p.trio_utils import (
    every,
)

from p2p.discv5.abc import (
    EnrDbApi,
    MessageDispatcherAPI,
)
from p2p.discv5.channel_services import (
    Endpoint,
    IncomingMessage,
    OutgoingMessage,
)
from p2p.discv5.constants import (
    REQUEST_RESPONSE_TIMEOUT,
    ROUTING_TABLE_PING_INTERVAL,
)
from p2p.discv5.endpoint_tracker import (
    EndpointVote,
)
from p2p.discv5.enr import (
    ENR,
)
from p2p.discv5.messages import (
    FindNodeMessage,
    NodesMessage,
    PingMessage,
    PongMessage,
)
from p2p.discv5.routing_table import (
    FlatRoutingTable,
)
from p2p.discv5.typing import (
    NodeID,
)


class BaseRoutingTableManagerComponent(Service):
    """Base class for services that participate in managing the routing table."""

    logger = logging.getLogger("p2p.discv5.routing_table_manager.BaseRoutingTableManagerComponent")

    def __init__(self,
                 local_node_id: NodeID,
                 routing_table: FlatRoutingTable,
                 message_dispatcher: MessageDispatcherAPI,
                 enr_db: EnrDbApi,
                 ) -> None:
        self.local_node_id = local_node_id
        self.routing_table = routing_table
        self.message_dispatcher = message_dispatcher
        self.enr_db = enr_db

    def update_routing_table(self, node_id: NodeID) -> None:
        """Update a peer's entry in the routing table.

        This method should be called, whenever we receive a message from them.
        """
        self.logger.debug("Updating %s in routing table", encode_hex(node_id))
        self.routing_table.add_or_update(node_id)

    async def get_local_enr(self) -> ENR:
        """Get the local enr from the ENR DB."""
        try:
            local_enr = await self.enr_db.get(self.local_node_id)
        except KeyError:
            raise ValueError(
                f"Local ENR with node id {encode_hex(self.local_node_id)} not "
                f"present in db"
            )
        else:
            return local_enr

    async def maybe_request_remote_enr(self, incoming_message: IncomingMessage) -> None:
        """Request the peers ENR if there is a newer version according to a ping or pong."""
        if not isinstance(incoming_message.message, (PingMessage, PongMessage)):
            raise TypeError(
                f"Only ping and pong messages contain an ENR sequence number, got "
                f"{incoming_message}"
            )

        try:
            remote_enr = await self.enr_db.get(incoming_message.sender_node_id)
        except KeyError:
            self.logger.warning(
                "No ENR of %s present in the database even though it should post handshake. "
                "Requesting it now.",
                encode_hex(incoming_message.sender_node_id)
            )
            request_update = True
        else:
            current_sequence_number = remote_enr.sequence_number
            advertized_sequence_number = incoming_message.message.enr_seq

            if current_sequence_number < advertized_sequence_number:
                self.logger.debug(
                    "ENR advertized by %s is newer than ours (sequence number %d > %d)",
                    encode_hex(incoming_message.sender_node_id),
                    advertized_sequence_number,
                    current_sequence_number,
                )
                request_update = True
            elif current_sequence_number == advertized_sequence_number:
                self.logger.debug(
                    "ENR of %s is up to date (sequence number %d)",
                    encode_hex(incoming_message.sender_node_id),
                    advertized_sequence_number,
                )
                request_update = False
            elif current_sequence_number > advertized_sequence_number:
                self.logger.warning(
                    "Peer %s advertizes apparently outdated ENR (sequence number %d < %d)",
                    encode_hex(incoming_message.sender_node_id),
                    advertized_sequence_number,
                    current_sequence_number,
                )
                request_update = False
            else:
                raise Exception("Invariant: Unreachable")

        if request_update:
            await self.request_remote_enr(incoming_message)

    async def request_remote_enr(self, incoming_message: IncomingMessage) -> None:
        """Request the ENR of the sender of an incoming message and store it in the ENR db."""
        self.logger.debug("Requesting ENR from %s", encode_hex(incoming_message.sender_node_id))

        find_nodes_message = FindNodeMessage(
            request_id=self.message_dispatcher.get_free_request_id(incoming_message.sender_node_id),
            distance=0,  # request enr of the peer directly
        )
        try:
            with trio.fail_after(REQUEST_RESPONSE_TIMEOUT):
                response = await self.message_dispatcher.request(
                    incoming_message.sender_node_id,
                    find_nodes_message,
                    endpoint=incoming_message.sender_endpoint,
                )
        except trio.TooSlowError:
            self.logger.warning(
                "FindNode request to %s has timed out",
                encode_hex(incoming_message.sender_node_id),
            )
            return

        sender_node_id = response.sender_node_id
        self.update_routing_table(sender_node_id)

        if not isinstance(response.message, NodesMessage):
            self.logger.warning(
                "Peer %s responded to FindNode with %s instead of Nodes message",
                encode_hex(sender_node_id),
                response.message.__class__.__name__,
            )
            return
        self.logger.debug("Received Nodes message from %s", encode_hex(sender_node_id))

        if len(response.message.enrs) == 0:
            self.logger.warning(
                "Peer %s responded to FindNode with an empty Nodes message",
                encode_hex(sender_node_id),
            )
        elif len(response.message.enrs) > 1:
            self.logger.warning(
                "Peer %s responded to FindNode with more than one ENR",
                encode_hex(incoming_message.sender_node_id),
            )

        for enr in response.message.enrs:
            if enr.node_id != sender_node_id:
                self.logger.warning(
                    "Peer %s responded to FindNode with ENR from %s",
                    encode_hex(sender_node_id),
                    encode_hex(response.message.enrs[0].node_id),
                )
            await self.enr_db.insert_or_update(enr)


class PingHandlerService(BaseRoutingTableManagerComponent):
    """Responds to Pings with Pongs and requests ENR updates."""

    logger = logging.getLogger("p2p.discv5.routing_table_manager.PingHandlerService")

    def __init__(self,
                 local_node_id: NodeID,
                 routing_table: FlatRoutingTable,
                 message_dispatcher: MessageDispatcherAPI,
                 enr_db: EnrDbApi,
                 outgoing_message_send_channel: SendChannel[OutgoingMessage]
                 ) -> None:
        super().__init__(local_node_id, routing_table, message_dispatcher, enr_db)
        self.outgoing_message_send_channel = outgoing_message_send_channel

    async def run(self) -> None:
        channel_handler_subscription = self.message_dispatcher.add_request_handler(PingMessage)
        async with channel_handler_subscription:
            async for incoming_message in channel_handler_subscription:
                self.logger.debug(
                    "Handling %s from %s",
                    incoming_message,
                    encode_hex(incoming_message.sender_node_id),
                )
                self.update_routing_table(incoming_message.sender_node_id)
                await self.respond_with_pong(incoming_message)
                self.manager.run_task(self.maybe_request_remote_enr, incoming_message)

    async def respond_with_pong(self, incoming_message: IncomingMessage) -> None:
        if not isinstance(incoming_message.message, PingMessage):
            raise TypeError(
                f"Can only respond with Pong to Ping, not "
                f"{incoming_message.message.__class__.__name__}"
            )

        local_enr = await self.get_local_enr()

        pong = PongMessage(
            request_id=incoming_message.message.request_id,
            enr_seq=local_enr.sequence_number,
            packet_ip=incoming_message.sender_endpoint.ip_address,
            packet_port=incoming_message.sender_endpoint.port,
        )
        outgoing_message = incoming_message.to_response(pong)
        self.logger.debug(
            "Responding with Pong to %s",
            encode_hex(outgoing_message.receiver_node_id),
        )
        await self.outgoing_message_send_channel.send(outgoing_message)


class FindNodeHandlerService(BaseRoutingTableManagerComponent):
    """Responds to FindNode with Nodes messages."""

    logger = logging.getLogger("p2p.discv5.routing_table_manager.FindNodeHandlerService")

    def __init__(self,
                 local_node_id: NodeID,
                 routing_table: FlatRoutingTable,
                 message_dispatcher: MessageDispatcherAPI,
                 enr_db: EnrDbApi,
                 outgoing_message_send_channel: SendChannel[OutgoingMessage]
                 ) -> None:
        super().__init__(local_node_id, routing_table, message_dispatcher, enr_db)
        self.outgoing_message_send_channel = outgoing_message_send_channel

    async def run(self) -> None:
        handler_subscription = self.message_dispatcher.add_request_handler(FindNodeMessage)
        async with handler_subscription:
            async for incoming_message in handler_subscription:
                self.update_routing_table(incoming_message.sender_node_id)

                if not isinstance(incoming_message.message, FindNodeMessage):
                    raise TypeError(
                        f"Received {incoming_message.__class__.__name__} from message dispatcher "
                        f"even though we subscribed to FindNode messages"
                    )

                if incoming_message.message.distance == 0:
                    await self.respond_with_local_enr(incoming_message)
                else:
                    self.logger.warning(
                        "Received FindNode request for non-zero distance from %s which is not "
                        "implemented yet",
                        encode_hex(incoming_message.sender_node_id),
                    )

    async def respond_with_local_enr(self, incoming_message: IncomingMessage) -> None:
        """Send a Nodes message containing the local ENR in response to an incoming message."""
        local_enr = await self.get_local_enr()
        nodes_message = NodesMessage(
            request_id=incoming_message.message.request_id,
            total=1,
            enrs=(local_enr,),
        )
        outgoing_message = incoming_message.to_response(nodes_message)

        self.logger.debug(
            "Responding to %s with Nodes message containing local ENR",
            incoming_message.sender_endpoint,
        )
        await self.outgoing_message_send_channel.send(outgoing_message)


class PingSenderService(BaseRoutingTableManagerComponent):
    """Regularly sends pings to peers to check if they are still alive or not."""

    logger = logging.getLogger("p2p.discv5.routing_table_manager.PingSenderService")

    def __init__(self,
                 local_node_id: NodeID,
                 routing_table: FlatRoutingTable,
                 message_dispatcher: MessageDispatcherAPI,
                 enr_db: EnrDbApi,
                 endpoint_vote_send_channel: SendChannel[EndpointVote]
                 ) -> None:
        super().__init__(local_node_id, routing_table, message_dispatcher, enr_db)
        self.endpoint_vote_send_channel = endpoint_vote_send_channel

    async def run(self) -> None:
        async for _ in every(ROUTING_TABLE_PING_INTERVAL):  # noqa: F841
            if len(self.routing_table) > 0:
                node_id = self.routing_table.get_oldest_entry()
                self.logger.debug("Pinging %s", encode_hex(node_id))
                await self.ping(node_id)
            else:
                self.logger.warning("Routing table is empty, no one to ping")

    async def ping(self, node_id: NodeID) -> None:
        local_enr = await self.get_local_enr()
        ping = PingMessage(
            request_id=self.message_dispatcher.get_free_request_id(node_id),
            enr_seq=local_enr.sequence_number,
        )

        try:
            with trio.fail_after(REQUEST_RESPONSE_TIMEOUT):
                incoming_message = await self.message_dispatcher.request(node_id, ping)
        except ValueError as value_error:
            self.logger.warning(
                f"Failed to send ping to %s: %s",
                encode_hex(node_id),
                value_error,
            )
        except trio.TooSlowError:
            self.logger.warning(f"Ping to %s timed out", encode_hex(node_id))
        else:
            if not isinstance(incoming_message.message, PongMessage):
                self.logger.warning(
                    "Peer %s responded to Ping with %s instead of Pong",
                    encode_hex(node_id),
                    incoming_message.message.__class__.__name__,
                )
            else:
                self.logger.debug("Received Pong from %s", encode_hex(node_id))

                self.update_routing_table(node_id)

                pong = incoming_message.message
                local_endpoint = Endpoint(
                    ip_address=pong.packet_ip,
                    port=pong.packet_port,
                )
                endpoint_vote = EndpointVote(
                    endpoint=local_endpoint,
                    node_id=node_id,
                    timestamp=time.monotonic(),
                )
                await self.endpoint_vote_send_channel.send(endpoint_vote)

                await self.maybe_request_remote_enr(incoming_message)


class RoutingTableManager(Service):
    """Manages the routing table. The actual work is delegated to a few sub components."""

    def __init__(self,
                 local_node_id: NodeID,
                 routing_table: FlatRoutingTable,
                 message_dispatcher: MessageDispatcherAPI,
                 enr_db: EnrDbApi,
                 outgoing_message_send_channel: SendChannel[OutgoingMessage],
                 endpoint_vote_send_channel: SendChannel[EndpointVote],
                 ) -> None:
        SharedComponentKwargType = TypedDict("SharedComponentKwargType", {
            "local_node_id": NodeID,
            "routing_table": FlatRoutingTable,
            "message_dispatcher": MessageDispatcherAPI,
            "enr_db": EnrDbApi,
        })
        shared_component_kwargs = SharedComponentKwargType({
            "local_node_id": local_node_id,
            "routing_table": routing_table,
            "message_dispatcher": message_dispatcher,
            "enr_db": enr_db,
        })

        self.ping_handler_service = PingHandlerService(
            outgoing_message_send_channel=outgoing_message_send_channel,
            **shared_component_kwargs,
        )
        self.find_node_handler_service = FindNodeHandlerService(
            outgoing_message_send_channel=outgoing_message_send_channel,
            **shared_component_kwargs,
        )
        self.ping_sender_service = PingSenderService(
            endpoint_vote_send_channel=endpoint_vote_send_channel,
            **shared_component_kwargs,
        )

    async def run(self) -> None:
        child_services = (
            self.ping_handler_service,
            self.find_node_handler_service,
            self.ping_sender_service,
        )
        for child_service in child_services:
            self.manager.run_daemon_child_service(child_service)

        await self.manager.wait_finished()
