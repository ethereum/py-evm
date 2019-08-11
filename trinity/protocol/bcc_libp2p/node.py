import asyncio
from typing import (
    Dict,
    List,
    Optional,
    Set,
    Sequence,
    Tuple,
)

from cancel_token import (
    CancelToken,
)

from eth_keys import (
    datatypes,
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
from libp2p.security.secure_transport_interface import (
    ISecureTransport,
)

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
)
from .messages import (
    HelloRequest,
)
from .utils import (
    make_rpc_v1_ssz_protocol_id,
    make_tcp_ip_maddr,
    peer_id_from_pubkey,
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

    privkey: datatypes.PrivateKey
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
            privkey: datatypes.PrivateKey,
            listen_ip: str,
            listen_port: int,
            security_protocol_ops: Dict[str, ISecureTransport],
            muxer_protocol_ids: Tuple[str, ...],
            chain: BaseBeaconChain,
            gossipsub_params: Optional[GossipsubParams] = None,
            cancel_token: CancelToken = None,
            bootstrap_nodes: Tuple[Multiaddr, ...] = None,
            preferred_nodes: Tuple[Multiaddr, ...] = None) -> None:
        super().__init__(cancel_token)
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.privkey = privkey
        self.bootstrap_nodes = bootstrap_nodes
        self.preferred_nodes = preferred_nodes
        # TODO: Add key and peer_id to the peerstore
        network: INetwork = initialize_default_swarm(
            id_opt=peer_id_from_pubkey(self.privkey.public_key),
            transport_opt=[self.listen_maddr],
            muxer_opt=list(muxer_protocol_ids),
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
        self.logger.info(f"libp2p node up")
        self.run_daemon_task(self.start())
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

    async def _validate_hello_req(self, hello_other_side: HelloRequest) -> bool:
        state = self.chain.get_state_machine().state
        if hello_other_side.fork_version != state.fork.current_version:
            return False
        finalized_checkpoint = state.finalized_checkpoint
        # TODO: Reject if the (finalized_root, finalized_epoch) shared by the peer
        #   is not in the client's chain at the expected epoch.
        #   - If our `finalized_epoch` is larger
        # if finalized_checkpoint.epoch > hello_other_side.finalized_epoch:
        #     our_root_at_peer_finalized_epoch = chain.
        return True

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
        # TODO: Handle `stream.close` and `stream.reset`
        peer_id = stream.mplex_conn.peer_id
        if peer_id in self.handshaked_peers:
            self.logger.info(f"Handshake failed: already handshaked with {peer_id} before.")
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            return

        self.logger.debug(f"Waiting for hello from the other side")
        try:
            hello_other_side = await read_req(stream, HelloRequest)
        except asyncio.TimeoutError:
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            return
        self.logger.debug(f"Received the hello message {hello_other_side}")
        if not (await self._validate_hello_req(hello_other_side)):
            self.logger.info(
                f"Handshake failed: hello message {hello_other_side} is not valid."
                f"Disconnecting {peer_id}."
            )
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            return

        hello_mine = self._make_hello_packet()

        self.logger.debug(f"Sending our hello message {hello_mine}")
        # TODO: Find out when we should respond the `ResponseCode`
        #   other than `ResponseCode.SUCCESS`.
        await write_resp(stream, hello_mine, ResponseCode.SUCCESS)

        self.handshaked_peers.add(peer_id)

        self.logger.debug(f"Handshake from {peer_id} is finished. Added to the `handshake_peers`.")
        # TODO: If we have lower `finalized_epoch` or `head_slot`, request the later beacon blocks.

    async def say_hello(self, peer_id: ID) -> None:
        # TODO: Handle `stream.close` and `stream.reset`
        if peer_id in self.handshaked_peers:
            error_msg = f"already handshaked with {peer_id} before"
            self.logger.info(f"Handshake failed: {error_msg}.")
            raise HandshakeFailure(error_msg)

        hello_mine = self._make_hello_packet()

        self.logger.debug(f"Opening new stream to {peer_id} with protocols {[REQ_RESP_HELLO_SSZ]}.")
        stream = await self.host.new_stream(peer_id, [REQ_RESP_HELLO_SSZ])
        self.logger.debug(f"Sending our hello message {hello_mine}.")
        await write_req(stream, hello_mine)

        self.logger.debug(f"Waiting for hello from the other side")
        try:
            resp_code, hello_other_side = await read_resp(stream, HelloRequest)
        except asyncio.TimeoutError:
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            raise HandshakeFailure("time out when reading the response")

        self.logger.debug(f"Received the hello message {hello_other_side}, resp_code={resp_code}.")

        # TODO: Handle the case when `resp_code` is not success.
        if resp_code != ResponseCode.SUCCESS:
            # TODO: Do something according to the `ResponseCode`
            # TODO: Disconnect
            error_msg = (
                f"resp_code != ResponseCode.SUCCESS, "
                "resp_code={resp_code}, error_msg={hello_other_side}"
            )
            self.logger.info(f"Handshake failed: {error_msg}")
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            raise HandshakeFailure(error_msg)

        if not (await self._validate_hello_req(hello_other_side)):
            error_msg = f"hello message {hello_other_side} is invalid"
            self.logger.info(f"Handshake failed: {error_msg}. Disconnecting {peer_id}.")
            # FIXME: Use `Stream.reset()` when `NetStream` has this API.
            # await stream.reset()
            # TODO: Disconnect
            raise HandshakeFailure(error_msg)

        self.handshaked_peers.add(peer_id)

        self.logger.debug(f"Handshake to {peer_id} is finished. Added to the `handshake_peers`.")
        # TODO: If we have lower `finalized_epoch` or `head_slot`, request the later beacon blocks.
