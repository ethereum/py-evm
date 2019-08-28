from typing import (
    cast,
    Any,
    AsyncContextManager,
    Tuple,
    Type,
)

from lahja import EndpointAPI

from cancel_token import CancelToken

from eth_utils import to_bytes

from eth_keys import keys

from eth.db.header import HeaderDB
from eth.db.backends.memory import MemoryDB
from eth.db.atomic import AtomicDB
from eth.constants import GENESIS_DIFFICULTY, GENESIS_BLOCK_NUMBER
from eth.chains.mainnet import MAINNET_VM_CONFIGURATION

from p2p import kademlia
from p2p.handshake import Handshaker
from p2p.tools.factories import PeerPairFactory

from trinity.constants import MAINNET_NETWORK_ID
from trinity.db.eth1.header import AsyncHeaderDB

from trinity.protocol.common.context import ChainContext

from trinity.protocol.eth.handshaker import ETHHandshaker
from trinity.protocol.eth.peer import ETHPeer, ETHPeerFactory
from trinity.protocol.eth.proto import ETHHandshakeParams, ETHProtocol

from trinity.protocol.les.handshaker import LESV2Handshaker, LESV1Handshaker
from trinity.protocol.les.peer import LESPeer, LESPeerFactory
from trinity.protocol.les.proto import LESHandshakeParams, LESProtocol, LESProtocolV2


try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")


MAINNET_GENESIS_HASH = to_bytes(hexstr='0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3')  # noqa: E501


class MemoryDBFactory(factory.Factory):
    class Meta:
        model = MemoryDB


class AtomicDBFactory(factory.Factory):
    class Meta:
        model = AtomicDB

    wrapped_db = factory.SubFactory(MemoryDBFactory)


class HeaderDBFactory(factory.Factory):
    class Meta:
        model = HeaderDB

    db = factory.SubFactory(AtomicDBFactory)


class AsyncHeaderDBFactory(factory.Factory):
    class Meta:
        model = AsyncHeaderDB

    db = factory.SubFactory(AtomicDBFactory)

    @classmethod
    def _create(cls,
                model_class: Type[AsyncHeaderDB],
                *args: Any,
                **kwargs: Any) -> AsyncHeaderDB:
        headerdb = model_class(*args, **kwargs)
        from eth.chains.base import Chain
        from eth.tools.builder.chain import build, latest_mainnet_at, genesis

        build(
            Chain,
            latest_mainnet_at(0),
            genesis(db=headerdb.db),
        )
        return headerdb


class ChainContextFactory(factory.Factory):
    class Meta:
        model = ChainContext

    network_id = 1
    client_version_string = 'test'
    headerdb = factory.SubFactory(AsyncHeaderDBFactory)
    vm_configuration = ((0, MAINNET_VM_CONFIGURATION[-1][1]),)
    listen_port = 30303
    p2p_version = 5


class ETHHandshakeParamsFactory(factory.Factory):
    class Meta:
        model = ETHHandshakeParams

    head_hash = MAINNET_GENESIS_HASH
    genesis_hash = MAINNET_GENESIS_HASH
    network_id = MAINNET_NETWORK_ID
    total_difficulty = GENESIS_DIFFICULTY
    version = ETHProtocol.version

    @classmethod
    def from_headerdb(cls, headerdb: HeaderDB, **kwargs: Any) -> ETHHandshakeParams:
        head = headerdb.get_canonical_head()
        head_score = headerdb.get_score(head.hash)
        genesis = headerdb.get_canonical_block_header_by_number(GENESIS_BLOCK_NUMBER)
        return cls(
            head_hash=head.hash,
            genesis_hash=genesis.hash,
            total_difficulty=head_score,
            **kwargs
        )


class ETHHandshakerFactory(factory.Factory):
    class Meta:
        model = ETHHandshaker

    handshake_params = factory.SubFactory(ETHHandshakeParamsFactory)


def ETHPeerPairFactory(*,
                       alice_peer_context: ChainContext = None,
                       alice_remote: kademlia.Node = None,
                       alice_private_key: keys.PrivateKey = None,
                       alice_client_version: str = 'bob',
                       bob_peer_context: ChainContext = None,
                       bob_remote: kademlia.Node = None,
                       bob_private_key: keys.PrivateKey = None,
                       bob_client_version: str = 'bob',
                       cancel_token: CancelToken = None,
                       event_bus: EndpointAPI = None,
                       ) -> AsyncContextManager[Tuple[ETHPeer, ETHPeer]]:
    if alice_peer_context is None:
        alice_peer_context = ChainContextFactory()
    if bob_peer_context is None:
        bob_peer_context = ChainContextFactory()

    return cast(AsyncContextManager[Tuple[ETHPeer, ETHPeer]], PeerPairFactory(
        alice_peer_context=alice_peer_context,
        alice_peer_factory_class=ETHPeerFactory,
        bob_peer_context=bob_peer_context,
        bob_peer_factory_class=ETHPeerFactory,
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        alice_client_version=alice_client_version,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
        bob_client_version=bob_client_version,
        cancel_token=cancel_token,
        event_bus=event_bus,
    ))


class LESHandshakeParamsFactory(factory.Factory):
    class Meta:
        model = LESHandshakeParams

    version = LESProtocolV2.version
    network_id = MAINNET_NETWORK_ID
    head_td = GENESIS_DIFFICULTY
    head_hash = MAINNET_GENESIS_HASH
    head_num = GENESIS_BLOCK_NUMBER
    genesis_hash = MAINNET_GENESIS_HASH
    serve_headers = True
    serve_chain_since = 0
    serve_state_since = None
    serve_recent_state = None
    serve_recent_chain = None
    tx_relay = False
    flow_control_bl = None
    flow_control_mcr = None
    flow_control_mrr = None
    announce_type = factory.LazyAttribute(
        lambda o: o.version if o.version >= LESProtocolV2.version else None
    )


class LESV1HandshakerFactory(factory.Factory):
    class Meta:
        model = LESV1Handshaker

    handshake_params = factory.SubFactory(LESHandshakeParamsFactory, version=LESProtocol.version)


class LESV2HandshakerFactory(factory.Factory):
    class Meta:
        model = LESV2Handshaker

    handshake_params = factory.SubFactory(LESHandshakeParamsFactory, version=LESProtocolV2.version)


class LESV1Peer(LESPeer):
    supported_sub_protocols = (LESProtocol,)  # type: ignore


class LESV1PeerFactory(LESPeerFactory):
    peer_class = LESV1Peer

    async def get_handshakers(self) -> Tuple[Handshaker, ...]:
        return (
            LESV1Handshaker(LESHandshakeParamsFactory(version=1)),
        )


def LESV1PeerPairFactory(*,
                         alice_peer_context: ChainContext = None,
                         alice_remote: kademlia.Node = None,
                         alice_private_key: keys.PrivateKey = None,
                         alice_client_version: str = 'alice',
                         bob_peer_context: ChainContext = None,
                         bob_remote: kademlia.Node = None,
                         bob_private_key: keys.PrivateKey = None,
                         bob_client_version: str = 'bob',
                         cancel_token: CancelToken = None,
                         event_bus: EndpointAPI = None,
                         ) -> AsyncContextManager[Tuple[LESV1Peer, LESV1Peer]]:
    if alice_peer_context is None:
        alice_peer_context = ChainContextFactory()
    if bob_peer_context is None:
        bob_peer_context = ChainContextFactory()

    return cast(AsyncContextManager[Tuple[LESV1Peer, LESV1Peer]], PeerPairFactory(
        alice_peer_context=alice_peer_context,
        alice_peer_factory_class=LESV1PeerFactory,
        bob_peer_context=bob_peer_context,
        bob_peer_factory_class=LESV1PeerFactory,
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        alice_client_version=alice_client_version,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
        bob_client_version=bob_client_version,
        cancel_token=cancel_token,
        event_bus=event_bus,
    ))


def LESV2PeerPairFactory(*,
                         alice_peer_context: ChainContext = None,
                         alice_remote: kademlia.Node = None,
                         alice_private_key: keys.PrivateKey = None,
                         alice_client_version: str = 'alice',
                         bob_peer_context: ChainContext = None,
                         bob_remote: kademlia.Node = None,
                         bob_private_key: keys.PrivateKey = None,
                         bob_client_version: str = 'bob',
                         cancel_token: CancelToken = None,
                         event_bus: EndpointAPI = None,
                         ) -> AsyncContextManager[Tuple[LESPeer, LESPeer]]:
    if alice_peer_context is None:
        alice_peer_context = ChainContextFactory()
    if bob_peer_context is None:
        bob_peer_context = ChainContextFactory()

    return cast(AsyncContextManager[Tuple[LESPeer, LESPeer]], PeerPairFactory(
        alice_peer_context=alice_peer_context,
        alice_peer_factory_class=LESPeerFactory,
        bob_peer_context=bob_peer_context,
        bob_peer_factory_class=LESPeerFactory,
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        alice_client_version=alice_client_version,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
        bob_client_version=bob_client_version,
        cancel_token=cancel_token,
        event_bus=event_bus,
    ))
