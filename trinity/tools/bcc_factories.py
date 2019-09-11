from eth2.beacon.tools.factories import BeaconChainFactory
import asyncio
from typing import (
    cast,
    Any,
    AsyncContextManager,
    AsyncIterator,
    Iterable,
    Tuple,
    Type,
)

from async_generator import asynccontextmanager

from lahja import EndpointAPI

from cancel_token import CancelToken

from libp2p.crypto.secp256k1 import create_new_key_pair

from eth_keys import keys

from eth_utils import to_tuple

from eth.constants import (
    ZERO_HASH32,
)

from p2p import kademlia
from p2p.constants import DEFAULT_MAX_PEERS
from p2p.service import run_service
from p2p.tools.factories import (
    get_open_port,
    CancelTokenFactory,
    PeerPairFactory,
    PrivateKeyFactory,
)

from eth2.beacon.constants import EMPTY_SIGNATURE, ZERO_SIGNING_ROOT
from eth2.beacon.fork_choice.higher_slot import higher_slot_scoring
from eth2.beacon.types.blocks import (
    BeaconBlock,
    BeaconBlockBody,
    BaseBeaconBlock,
)
from eth2.beacon.state_machines.forks.serenity import SERENITY_CONFIG
from eth2.configs import (
    Eth2GenesisConfig,
)

from trinity.db.beacon.chain import AsyncBeaconChainDB

from trinity.protocol.bcc.context import BeaconContext
from trinity.protocol.bcc.peer import (
    BCCPeer,
    BCCPeerFactory,
    BCCPeerPool,
)

from trinity.protocol.bcc_libp2p.node import Node, PeerPool
from trinity.protocol.bcc_libp2p.servers import BCCReceiveServer
from trinity.sync.beacon.chain import BeaconChainSyncer

from .factories import (
    AtomicDBFactory,
)


try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")


SERENITY_GENESIS_CONFIG = Eth2GenesisConfig(SERENITY_CONFIG)


#
# LibP2P
#


class NodeFactory(factory.Factory):
    class Meta:
        model = Node

    key_pair = factory.LazyFunction(create_new_key_pair)
    listen_ip = "127.0.0.1"
    listen_port = factory.LazyFunction(get_open_port)
    security_protocol_ops = None
    muxer_protocol_ops = None
    gossipsub_params = None
    cancel_token = None
    bootstrap_nodes = None
    preferred_nodes = None
    chain = factory.SubFactory(BeaconChainFactory)

    @classmethod
    def create_batch(cls, number: int) -> Tuple[Node, ...]:
        return tuple(
            cls() for _ in range(number)
        )


@asynccontextmanager
async def ConnectionPairFactory(
    alice_chaindb: AsyncBeaconChainDB = None,
    bob_chaindb: AsyncBeaconChainDB = None,
    cancel_token: CancelToken = None,
    say_hello: bool = True,
) -> AsyncIterator[Tuple[Node, Node]]:
    if cancel_token is None:
        cancel_token = CancelTokenFactory()
    alice = NodeFactory(chain__db=alice_chaindb.db, cancel_token=cancel_token)
    bob = NodeFactory(chain__db=bob_chaindb.db, cancel_token=cancel_token)
    async with run_service(alice), run_service(bob):
        await asyncio.sleep(0.01)
        await alice.dial_peer_maddr(bob.listen_maddr_with_peer_id)
        await asyncio.sleep(0.01)
        if say_hello:
            await alice.say_hello(bob.peer_id)
            await asyncio.sleep(0.01)
        yield alice, bob


class BeaconBlockBodyFactory(factory.Factory):
    class Meta:
        model = BeaconBlockBody


class BeaconBlockFactory(factory.Factory):
    class Meta:
        model = BeaconBlock

    slot = SERENITY_GENESIS_CONFIG.GENESIS_SLOT
    parent_root = ZERO_SIGNING_ROOT
    state_root = ZERO_HASH32
    signature = EMPTY_SIGNATURE
    body = factory.SubFactory(BeaconBlockBodyFactory)

    @classmethod
    def _create(cls, model_class: Type[BeaconBlock], *args: Any, **kwargs: Any) -> BeaconBlock:
        parent = kwargs.pop('parent', None)
        if parent is not None:
            kwargs['parent_root'] = parent.signing_root
            kwargs['slot'] = parent.slot + 1
        return super()._create(model_class, *args, **kwargs)

    @classmethod
    @to_tuple
    def create_branch(cls,
                      length: int,
                      root: BeaconBlock=None,
                      **kwargs: Any) -> Iterable[BeaconBlock]:
        if length == 0:
            return

        if root is None:
            root = cls()

        parent = cls(parent=root, **kwargs)
        yield parent

        for _ in range(length - 1):
            child = cls(parent=parent)
            yield child
            parent = child


class AsyncBeaconChainDBFactory(factory.Factory):
    class Meta:
        model = AsyncBeaconChainDB

    db = factory.SubFactory(AtomicDBFactory)
    genesis_config = SERENITY_GENESIS_CONFIG

    @classmethod
    def _create(cls,
                model_class: Type[AsyncBeaconChainDB],
                *args: Any,
                **kwargs: Any) -> AsyncBeaconChainDB:
        blocks = kwargs.pop('blocks', None)
        if blocks is None:
            blocks = (BeaconBlockFactory(),)
        chain_db = super()._create(model_class, *args, **kwargs)
        chain_db.persist_block_chain(
            blocks,
            BeaconBlock,
            (higher_slot_scoring,) * len(blocks)
        )
        return chain_db


class BeaconContextFactory(factory.Factory):
    class Meta:
        model = BeaconContext

    chain_db = factory.SubFactory(AsyncBeaconChainDBFactory)
    network_id = 1
    client_version_string = 'alice'
    listen_port = 30303
    p2p_version = 5


def BCCPeerPairFactory(*,
                       alice_peer_context: BeaconContext = None,
                       alice_remote: kademlia.Node = None,
                       alice_private_key: keys.PrivateKey = None,
                       alice_client_version: str = 'alice',
                       bob_peer_context: BeaconContext = None,
                       bob_remote: kademlia.Node = None,
                       bob_private_key: keys.PrivateKey = None,
                       bob_client_version: str = 'bob',
                       cancel_token: CancelToken = None,
                       event_bus: EndpointAPI = None,
                       ) -> AsyncContextManager[Tuple[BCCPeer, BCCPeer]]:
    if alice_peer_context is None:
        alice_peer_context = BeaconContextFactory()
    if bob_peer_context is None:
        bob_peer_context = BeaconContextFactory()

    return cast(AsyncContextManager[Tuple[BCCPeer, BCCPeer]], PeerPairFactory(
        alice_peer_context=alice_peer_context,
        alice_peer_factory_class=BCCPeerFactory,
        bob_peer_context=bob_peer_context,
        bob_peer_factory_class=BCCPeerFactory,
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        alice_client_version=alice_client_version,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
        bob_client_version=bob_client_version,
        cancel_token=cancel_token,
        event_bus=event_bus,
    ))


class BCCPeerPoolFactory(factory.Factory):
    class Meta:
        model = BCCPeerPool

    privkey = factory.LazyFunction(PrivateKeyFactory)
    context = factory.SubFactory(BeaconContextFactory)
    max_peers = DEFAULT_MAX_PEERS
    token = factory.LazyFunction(CancelTokenFactory)
    event_bus = None

    @classmethod
    @asynccontextmanager
    async def run_for_peer(cls, peer: BCCPeer, **kwargs: Any) -> AsyncIterator[BCCPeerPool]:
        kwargs.setdefault('event_bus', peer.get_event_bus())
        peer_pool = cls(**kwargs)

        async with run_service(peer_pool):
            peer_pool._add_peer(peer, ())
            yield peer_pool


class ReceiveServerFactory(factory.Factory):
    class Meta:
        model = BCCReceiveServer

    chain = None
    p2p_node = factory.SubFactory(NodeFactory)
    topic_msg_queues = None
    cancel_token = None

    @classmethod
    def create_batch(cls, number: int) -> Tuple[Node, ...]:
        return tuple(cls() for _ in range(number))


class SimpleWriterBlockImporter:
    """
    ``SimpleWriterBlockImporter`` just persists any imported blocks to the
    database provided at instantiation.
    """

    def __init__(self, chain_db: AsyncBeaconChainDB) -> None:
        self._chain_db = chain_db

    def import_block(
        self, block: BaseBeaconBlock
    ) -> Tuple[
        BaseBeaconBlock, Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]
    ]:
        new_blocks, old_blocks = self._chain_db.persist_block(
            block, BeaconBlock, higher_slot_scoring
        )
        return None, new_blocks, old_blocks


class BeaconChainSyncerFactory(factory.Factory):
    class Meta:
        model = BeaconChainSyncer

    chain_db = factory.SubFactory(AsyncBeaconChainDBFactory)
    peer_pool = factory.LazyAttribute(lambda _: PeerPool())
    block_importer = factory.LazyAttribute(
        lambda obj: SimpleWriterBlockImporter(obj.chain_db)
    )
    genesis_config = SERENITY_GENESIS_CONFIG
    token = None
