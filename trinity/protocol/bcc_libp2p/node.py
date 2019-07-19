import asyncio
from typing import (
    Dict,
    Optional,
    Sequence,
    Tuple,
)

from cancel_token import (
    CancelToken,
)

from eth_keys import (
    datatypes,
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
from libp2p.peer.id import (
    ID,
    id_b58_decode,
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
    PUBSUB_TOPIC_BEACON_BLOCK,
    PUBSUB_TOPIC_BEACON_ATTESTATION,
    GossipsubParams,
)
from .utils import (
    make_tcp_ip_maddr,
    peer_id_from_pubkey,
)


class Node(BaseService):

    privkey: datatypes.PrivateKey
    listen_ip: str
    listen_port: int
    host: BasicHost
    pubsub: Pubsub
    bootstrap_nodes: Optional[Tuple[Multiaddr, ...]]
    preferred_nodes: Optional[Tuple[Multiaddr, ...]]

    def __init__(
            self,
            privkey: datatypes.PrivateKey,
            listen_ip: str,
            listen_port: int,
            security_protocol_ops: Dict[str, ISecureTransport],
            muxer_protocol_ids: Tuple[str, ...],
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

    async def _run(self) -> None:
        self.logger.info(f"libp2p node up")
        self.run_daemon_task(self.start())
        await self.cancellation()

    async def start(self) -> None:
        # host
        await self.host.get_network().listen(self.listen_maddr)
        await self.connect_preferred_nodes()
        # TODO: Connect bootstrap nodes?
        # TODO: Set up stream handlers for each protocol
        # TODO: Register notifees

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
        Dial the peer ``peer_id`` through the IPv4 protocol
        """
        ip = maddr.value_for_protocol(protocols.P_IP4)
        port = maddr.value_for_protocol(protocols.P_TCP)
        peer_id = id_b58_decode(maddr.value_for_protocol(protocols.P_P2P))
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
        # TODO: Use `pubsub.publish` when it is finished in the upstream
        # await self.pubsub.publish(topic, data)
        pass

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
