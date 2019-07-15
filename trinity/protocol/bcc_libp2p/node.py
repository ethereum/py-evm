from typing import (
    Dict,
    List,
    Optional,
)

from cancel_token import (
    CancelToken,
)

from eth_keys import (
    datatypes,
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
)

from p2p.service import (
    BaseService,
)

from .configs import (
    PUBSUB_PROTOCOL_ID,
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

    def __init__(
            self,
            privkey: datatypes.PrivateKey,
            listen_ip: str,
            listen_port: int,
            security_protocol_ops: Dict[str, ISecureTransport],
            muxer_protocol_ids: List[str],
            gossipsub_params: Optional[GossipsubParams] = None,
            cancel_token: CancelToken = None) -> None:
        super().__init__(cancel_token)
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.privkey = privkey
        # TODO: Add key and peer_id to the peerstore
        network: INetwork = initialize_default_swarm(
            id_opt=peer_id_from_pubkey(self.privkey.public_key),
            transport_opt=[self.listen_maddr],
            muxer_opt=muxer_protocol_ids,
            sec_opt=security_protocol_ops,
            peerstore_opt=None,  # let the function initialize it
            disc_opt=None,  # no routing required here
        )
        self.host = BasicHost(network=network, router=None)

        if gossipsub_params is None:
            gossipsub_params = GossipsubParams()
        gossipsub_router = GossipSub(
            protocols=[PUBSUB_PROTOCOL_ID],
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
        self.run_daemon_task(self.listen())
        await self.cancellation()

    async def listen(self) -> None:
        await self.host.get_network().listen(self.listen_maddr)

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

    @property
    def peer_id(self) -> ID:
        return self.host.get_id()

    @property
    def listen_maddr(self) -> Multiaddr:
        return make_tcp_ip_maddr(self.listen_ip, self.listen_port)

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
