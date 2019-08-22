import asyncio
from typing import (
    Dict,
    Optional,
    Set,
    Sequence,
    Tuple,
)

from cancel_token import (
    CancelToken,
)

from eth2.beacon.chains.base import (
    BaseBeaconChain,
)
from eth2.beacon.types.attestations import (
    Attestation,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)

from libp2p import (
    initialize_default_swarm,
)
from libp2p.typing import TProtocol

from libp2p.crypto.keys import (
    KeyPair,
)
from libp2p.host.basic_host import (
    BasicHost,
)
from libp2p.network.network_interface import (
    INetwork,
)
from libp2p.network.stream.net_stream_interface import (
    INetStream,
)
from libp2p.peer.id import (
    ID,
)
from libp2p.peer.peerdata import (
    PeerData,
)
from libp2p.peer.peerinfo import (
    PeerInfo,
)
from libp2p.peer.peerstore import (
    PeerStore,
)
from libp2p.pubsub.pubsub import (
    Pubsub,
)
from libp2p.pubsub.gossipsub import (
    GossipSub,
)
from libp2p.security.base_transport import BaseSecureTransport
from libp2p.security.insecure.transport import PLAINTEXT_PROTOCOL_ID, InsecureTransport
from libp2p.stream_muxer.abc import IMuxedConn
from libp2p.stream_muxer.mplex.mplex import MPLEX_PROTOCOL_ID, Mplex

from multiaddr import (
    Multiaddr,
    protocols,
)

import ssz

from p2p.service import (
    BaseService,
)

from .configs import (
    GOSSIPSUB_PROTOCOL_ID,
    GossipsubParams,
    PUBSUB_TOPIC_BEACON_BLOCK,
    PUBSUB_TOPIC_BEACON_ATTESTATION,
    REQ_RESP_BEACON_BLOCKS,
    REQ_RESP_GOODBYE,
    REQ_RESP_HELLO,
    REQ_RESP_RECENT_BEACON_BLOCKS,
    ResponseCode,
)
from .exceptions import (
    HandshakeFailure,
    ReadMessageFailure,
    ValidationError,
    WriteMessageFailure,
)
from .messages import (
    HelloRequest,
)
from .utils import (
    make_rpc_v1_ssz_protocol_id,
    make_tcp_ip_maddr,
    read_req,
    read_resp,
    write_req,
    write_resp,
)


REQ_RESP_HELLO_SSZ = make_rpc_v1_ssz_protocol_id(REQ_RESP_HELLO)
REQ_RESP_GOODBYE_SSZ = make_rpc_v1_ssz_protocol_id(REQ_RESP_GOODBYE)
REQ_RESP_BEACON_BLOCKS_SSZ = make_rpc_v1_ssz_protocol_id(REQ_RESP_BEACON_BLOCKS)
REQ_RESP_RECENT_BEACON_BLOCKS_SSZ = make_rpc_v1_ssz_protocol_id(REQ_RESP_RECENT_BEACON_BLOCKS)


class Node(BaseService):

    key_pair: KeyPair
    listen_ip: str
    listen_port: int
    host: BasicHost
    pubsub: Pubsub
    bootstrap_nodes: Optional[Tuple[Multiaddr, ...]]
    preferred_nodes: Optional[Tuple[Multiaddr, ...]]
    chain: BaseBeaconChain

    handshaked_peers: Set[ID]

    def __init__(
            self,
            key_pair: KeyPair,
            listen_ip: str,
            listen_port: int,
            chain: BaseBeaconChain,
            security_protocol_ops: Dict[TProtocol, BaseSecureTransport] = None,
            muxer_protocol_ops: Dict[TProtocol, IMuxedConn] = None,
            gossipsub_params: Optional[GossipsubParams] = None,
            cancel_token: CancelToken = None,
            bootstrap_nodes: Tuple[Multiaddr, ...] = None,
            preferred_nodes: Tuple[Multiaddr, ...] = None) -> None:
        super().__init__(cancel_token)
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.key_pair = key_pair
        self.bootstrap_nodes = bootstrap_nodes
        self.preferred_nodes = preferred_nodes
        # TODO: Add key and peer_id to the peerstore
        if security_protocol_ops is None:
            security_protocol_ops = {
                PLAINTEXT_PROTOCOL_ID: InsecureTransport(key_pair)
            }
        if muxer_protocol_ops is None:
            muxer_protocol_ops = {MPLEX_PROTOCOL_ID: Mplex}
        network: INetwork = initialize_default_swarm(
            key_pair=key_pair,
            transport_opt=[self.listen_maddr],
            muxer_opt=muxer_protocol_ops,
            sec_opt=security_protocol_ops,
            peerstore_opt=None,  # let the function initialize it
            disc_opt=None,  # no routing required here
        )
        self.host = BasicHost(network=network, router=None)

        if gossipsub_params is None:
            gossipsub_params = GossipsubParams()
        gossipsub_router = GossipSub(
            protocols=[GOSSIPSUB_PROTOCOL_ID],
            degree=gossipsub_params.DEGREE,
            degree_low=gossipsub_params.DEGREE_LOW,
            degree_high=gossipsub_params.DEGREE_HIGH,
            time_to_live=gossipsub_params.FANOUT_TTL,
            gossip_window=gossipsub_params.GOSSIP_WINDOW,
            gossip_history=gossipsub_params.GOSSIP_HISTORY,
            heartbeat_interval=gossipsub_params.HEARTBEAT_INTERVAL,
        )
        self.pubsub = Pubsub(
            host=self.host,
            router=gossipsub_router,
            my_id=self.peer_id,
        )

        self.chain = chain

        self.handshaked_peers = set()

    async def _run(self) -> None:
        self.run_daemon_task(self.start())
        self.logger.info("libp2p node %s is up", self.listen_maddr)
        await self.cancellation()

    async def start(self) -> None:
        # host
        self._register_rpc_handlers()
        # TODO: Register notifees
        await self.host.get_network().listen(self.listen_maddr)
        await self.connect_preferred_nodes()
        # TODO: Connect bootstrap nodes?

        # pubsub
        await self.pubsub.subscribe(PUBSUB_TOPIC_BEACON_BLOCK)
        await self.pubsub.subscribe(PUBSUB_TOPIC_BEACON_ATTESTATION)
        # TODO: Register topic validators

    async def dial_peer(self, ip: str, port: int, peer_id: ID) -> None:
        """
        Dial the peer ``peer_id`` through the IPv4 protocol
        """
        peer_data = PeerData()
        peer_data.addrs = [make_tcp_ip_maddr(ip, port)]
        await self.host.connect(
            PeerInfo(
                peer_id=peer_id,
                peer_data=peer_data,
            )
        )

    async def dial_peer_maddr(self, maddr: Multiaddr) -> None:
        """
        Parse `maddr`, get the ip:port and PeerID, and call `dial_peer` with the parameters.
        """
        ip = maddr.value_for_protocol(protocols.P_IP4)
        port = maddr.value_for_protocol(protocols.P_TCP)
        peer_id = ID.from_base58(maddr.value_for_protocol(protocols.P_P2P))
        await self.dial_peer(ip=ip, port=port, peer_id=peer_id)

    async def connect_preferred_nodes(self) -> None:
        if self.preferred_nodes is None:
            return
        await asyncio.wait([
            self.dial_peer_maddr(node_maddr)
            for node_maddr in self.preferred_nodes
        ])

    async def broadcast_beacon_block(self, block: BaseBeaconBlock) -> None:
        await self._broadcast_data(PUBSUB_TOPIC_BEACON_BLOCK, ssz.encode(block))

    async def broadcast_attestations(self, attestations: Sequence[Attestation]) -> None:
        await self._broadcast_data(PUBSUB_TOPIC_BEACON_ATTESTATION, ssz.encode(attestations))

    async def _broadcast_data(self, topic: str, data: bytes) -> None:
        await self.pubsub.publish(topic, data)

    @property
    def peer_id(self) -> ID:
        return self.host.get_id()

    @property
    def listen_maddr(self) -> Multiaddr:
        return make_tcp_ip_maddr(self.listen_ip, self.listen_port)

    @property
    def listen_maddr_with_peer_id(self) -> Multiaddr:
        return self.listen_maddr.encapsulate(Multiaddr(f"/p2p/{self.peer_id}"))

    @property
    def peer_store(self) -> PeerStore:
        return self.host.get_network().peerstore

    async def close(self) -> None:
        # FIXME: Add `tear_down` to `Swarm` in the upstream
        network = self.host.get_network()
        for listener in network.listeners.values():
            listener.server.close()
            await listener.server.wait_closed()
        # TODO: Add `close` in `Pubsub`

    def _register_rpc_handlers(self) -> None:
        self.host.set_stream_handler(REQ_RESP_HELLO_SSZ, self._handle_hello)

    #
    # RPC Handlers
    #

    # TODO: Add a wrapper or decorator to handle the exceptions in handlers,
    #   to close the streams safely. Probably starting from: if the function
    #   returns successfully, then close the stream. Otherwise, reset the stream.

    # TODO: Handle the reputation of peers. Deduct their scores and even disconnect when they
    #   behave.

    # TODO: Register notifee to the `Network` to
    #   - Record peers' joining time.
    #   - Disconnect peers when they fail to join in a certain amount of time.

    async def _validate_hello_req(self, hello_other_side: HelloRequest) -> None:
        state = self.chain.get_state_machine().state
        if hello_other_side.fork_version != state.fork.current_version:
            raise ValidationError(
                "`fork_version` mismatches: "
                f"hello_other_side.fork_version={hello_other_side.fork_version}, "
                f"state.fork.current_version={state.fork.current_version}"
            )
        # TODO: Reject if the (finalized_root, finalized_epoch) shared by the peer
        #   is not in the client's chain at the expected epoch.

    async def _request_beacon_blocks(self) -> None:
        """
        TODO:
        Once the handshake completes, the client with the lower `finalized_epoch` or
        `head_slot` (if the clients have equal `finalized_epochs`) SHOULD request beacon blocks
        from its counterparty via the BeaconBlocks request.
        """

    def _make_hello_packet(self) -> HelloRequest:
        state = self.chain.get_state_machine().state
        finalized_checkpoint = state.finalized_checkpoint
        return HelloRequest(
            fork_version=state.fork.current_version,
            finalized_root=finalized_checkpoint.root,
            finalized_epoch=finalized_checkpoint.epoch,
            head_root=state.hash_tree_root,
            head_slot=state.slot,
        )

    async def _handle_hello(self, stream: INetStream) -> None:
        # TODO: Find out when we should respond the `ResponseCode`
        #   other than `ResponseCode.SUCCESS`.

        # TODO: Handle `stream.close` and `stream.reset`
        peer_id = stream.mplex_conn.peer_id
        if peer_id in self.handshaked_peers:
            self.logger.info(
                "Handshake failed: already handshaked with %s before",
                peer_id,
            )
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            return

        self.logger.debug("Waiting for hello from the other side")
        try:
            hello_other_side = await read_req(stream, HelloRequest)
        except ReadMessageFailure as error:
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            return
        self.logger.debug("Received the hello message %s", hello_other_side)

        try:
            await self._validate_hello_req(hello_other_side)
        except ValidationError:
            self.logger.info("Handshake failed: hello message %s is invalid", hello_other_side)
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            return

        hello_mine = self._make_hello_packet()

        self.logger.debug("Sending our hello message %s", hello_mine)
        try:
            await write_resp(stream, hello_mine, ResponseCode.SUCCESS)
        except WriteMessageFailure as error:
            self.logger.info(
                "Handshake failed: failed to write message %s",
                hello_mine,
            )
            # await stream.reset()
            # TODO: Disconnect
            return

        self.handshaked_peers.add(peer_id)

        self.logger.debug(
            "Handshake from %s is finished. Added to the `handshake_peers`",
            peer_id,
        )
        # TODO: If we have lower `finalized_epoch` or `head_slot`, request the later beacon blocks.

        await stream.close()

    async def say_hello(self, peer_id: ID) -> None:
        # TODO: Handle `stream.close` and `stream.reset`
        if peer_id in self.handshaked_peers:
            error_msg = f"already handshaked with {peer_id} before"
            self.logger.info("Handshake failed: %s", error_msg)
            raise HandshakeFailure(error_msg)

        hello_mine = self._make_hello_packet()

        self.logger.debug(
            "Opening new stream to peer=%s with protocols=%s",
            peer_id,
            [REQ_RESP_HELLO_SSZ],
        )
        stream = await self.host.new_stream(peer_id, [REQ_RESP_HELLO_SSZ])
        self.logger.debug("Sending our hello message %s", hello_mine)
        try:
            await write_req(stream, hello_mine)
        except WriteMessageFailure as error:
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            error_msg = f"fail to write request={hello_mine}"
            self.logger.info("Handshake failed: %s", error_msg)
            raise HandshakeFailure(error_msg) from error

        self.logger.debug("Waiting for hello from the other side")
        try:
            resp_code, hello_other_side = await read_resp(stream, HelloRequest)
        except ReadMessageFailure as error:
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            error_msg = "fail to read the response"
            self.logger.info("Handshake failed: %s", error_msg)
            raise HandshakeFailure(error_msg) from error

        self.logger.debug(
            "Received the hello message %s, resp_code=%s",
            hello_other_side,
            resp_code,
        )

        # TODO: Handle the case when `resp_code` is not success.
        if resp_code != ResponseCode.SUCCESS:
            # TODO: Do something according to the `ResponseCode`
            # TODO: Disconnect
            error_msg = (
                "resp_code != ResponseCode.SUCCESS, "
                f"resp_code={resp_code}, error_msg={hello_other_side}"
            )
            self.logger.info("Handshake failed: %s", error_msg)
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            raise HandshakeFailure(error_msg)

        try:
            await self._validate_hello_req(hello_other_side)
        except ValidationError as error:
            error_msg = f"hello message {hello_other_side} is invalid: {str(error)}"
            self.logger.info(
                "Handshake failed: %s. Disconnecting %s",
                error_msg,
                peer_id,
            )
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            raise HandshakeFailure(error_msg) from error

        self.handshaked_peers.add(peer_id)

        self.logger.debug(
            "Handshake to peer=%s is finished. Added to the `handshake_peers`",
            peer_id,
        )
        # TODO: If we have lower `finalized_epoch` or `head_slot`, request the later beacon blocks.

        await stream.close()
