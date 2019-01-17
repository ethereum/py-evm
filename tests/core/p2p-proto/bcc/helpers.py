import asyncio

from cancel_token import CancelToken

from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    merge,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth.db.atomic import AtomicDB

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.types.blocks import (
    BeaconBlock,
    BeaconBlockBody,
)
from eth2.beacon.types.eth1_data import (
    Eth1Data,
)

from trinity.protocol.bcc.context import BeaconContext
from trinity.protocol.bcc.peer import (
    BCCPeerFactory,
    BCCPeerPool,
)

from p2p import ecies
from p2p.tools.paragon.helpers import (
    get_directly_linked_peers_without_handshake as _get_directly_linked_peers_without_handshake,
    get_directly_linked_peers as _get_directly_linked_peers,
)


def create_test_block(parent=None, **kwargs):
    defaults = {
        "slot": 0,
        "parent_root": ZERO_HASH32,
        "state_root": ZERO_HASH32,  # note: not the actual genesis state root
        "randao_reveal": ZERO_HASH32,
        "eth1_data": Eth1Data.create_empty_data(),
        "signature": (0, 0),
        "body": BeaconBlockBody.create_empty_body()
    }

    if parent is not None:
        kwargs["parent_root"] = parent.root
        kwargs["slot"] = parent.slot + 1

    return BeaconBlock(**merge(defaults, kwargs))


@to_tuple
def create_branch(length, root=None, **start_kwargs):
    if length == 0:
        return

    if root is None:
        root = create_test_block(slot=0)

    parent = create_test_block(parent=root, **start_kwargs)
    yield parent

    for slot in range(root.slot + 2, root.slot + length + 1):
        child = create_test_block(parent)
        yield child
        parent = child


def get_chain_db(blocks=()):
    db = AtomicDB()
    chain_db = BeaconChainDB(db)
    chain_db.persist_block_chain(blocks, BeaconBlock)
    return chain_db


def get_genesis_chain_db():
    genesis = create_test_block(slot=0)
    return get_chain_db((genesis,))


async def _setup_alice_and_bob_factories(alice_chain_db, bob_chain_db):
    cancel_token = CancelToken('trinity.get_directly_linked_peers_without_handshake')

    #
    # Alice
    #
    alice_context = BeaconContext(
        chain_db=alice_chain_db,
        network_id=1,
    )

    alice_factory = BCCPeerFactory(
        privkey=ecies.generate_privkey(),
        context=alice_context,
        token=cancel_token,
    )

    #
    # Bob
    #
    bob_context = BeaconContext(
        chain_db=bob_chain_db,
        network_id=1,
    )

    bob_factory = BCCPeerFactory(
        privkey=ecies.generate_privkey(),
        context=bob_context,
        token=cancel_token,
    )

    return alice_factory, bob_factory


async def get_directly_linked_peers_without_handshake(alice_chain_db, bob_chain_db):
    alice_factory, bob_factory = await _setup_alice_and_bob_factories(alice_chain_db, bob_chain_db)

    return await _get_directly_linked_peers_without_handshake(
        alice_factory=alice_factory,
        bob_factory=bob_factory,
    )


async def get_directly_linked_peers(request, event_loop, alice_chain_db, bob_chain_db):
    alice_factory, bob_factory = await _setup_alice_and_bob_factories(
        alice_chain_db,
        bob_chain_db,
    )

    return await _get_directly_linked_peers(
        request,
        event_loop,
        alice_factory=alice_factory,
        bob_factory=bob_factory,
    )


async def get_directly_linked_peers_in_peer_pools(request,
                                                  event_loop,
                                                  alice_chain_db,
                                                  bob_chain_db):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=alice_chain_db,
        bob_chain_db=bob_chain_db,
    )
    alice_peer_pool = BCCPeerPool(alice.privkey, alice.context)
    bob_peer_pool = BCCPeerPool(bob.privkey, bob.context)

    asyncio.ensure_future(alice_peer_pool.run())
    asyncio.ensure_future(bob_peer_pool.run())

    def finalizer():
        event_loop.run_until_complete(alice_peer_pool.cancel())
        event_loop.run_until_complete(bob_peer_pool.cancel())

    request.addfinalizer(finalizer)

    alice_peer_pool._add_peer(alice, [])
    bob_peer_pool._add_peer(bob, [])

    return alice, alice_peer_pool, bob, bob_peer_pool
