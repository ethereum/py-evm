import asyncio

from cancel_token import CancelToken

from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    merge,
)

from eth.db.atomic import AtomicDB
from eth.beacon.db.chain import BeaconChainDB
from eth.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlockBody,
)
from eth.constants import (
    ZERO_HASH32,
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


def empty_body():
    return BeaconBlockBody(
        proposer_slashings=(),
        casper_slashings=(),
        attestations=(),
        deposits=(),
        exits=(),
    )


def create_test_block(parent=None, **kwargs):
    defaults = {
        "slot": 0,
        "parent_root": ZERO_HASH32,
        "state_root": ZERO_HASH32,  # note: not the actual genesis state root
        "randao_reveal": ZERO_HASH32,
        "candidate_pow_receipt_root": ZERO_HASH32,
        "signature": (0, 0),
        "body": empty_body()
    }

    if parent is not None:
        kwargs["parent_root"] = parent.hash
        kwargs["slot"] = parent.slot + 1

    return BaseBeaconBlock(**merge(defaults, kwargs))


@to_tuple
def create_branch(length, root, **start_kwargs):
    if length == 0:
        return

    parent = create_test_block(parent=root, **start_kwargs)
    yield parent

    for slot in range(root.slot + 2, root.slot + length + 1):
        child = create_test_block(parent)
        yield child
        parent = child


def get_fresh_chain_db():
    db = AtomicDB()
    genesis_block = create_test_block(slot=0)

    chain_db = BeaconChainDB(db)
    chain_db.persist_block(genesis_block)

    return chain_db


async def _setup_alice_and_bob_factories(alice_chain_db=None, bob_chain_db=None):
    cancel_token = CancelToken('trinity.get_directly_linked_peers_without_handshake')

    #
    # Alice
    #
    if alice_chain_db is None:
        alice_chain_db = get_fresh_chain_db()

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
    if bob_chain_db is None:
        bob_chain_db = get_fresh_chain_db()

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


async def get_directly_linked_peers_without_handshake(alice_chain_db=None, bob_chain_db=None):
    alice_factory, bob_factory = await _setup_alice_and_bob_factories(alice_chain_db, bob_chain_db)

    return await _get_directly_linked_peers_without_handshake(
        alice_factory=alice_factory,
        bob_factory=bob_factory,
    )


async def get_directly_linked_peers(request, event_loop, alice_chain_db=None, bob_chain_db=None):
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


async def get_directly_linked_peers_in_peer_pools(request, event_loop, chain_db=None):
    alice, bob = await get_directly_linked_peers(request, event_loop, bob_chain_db=chain_db)
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
