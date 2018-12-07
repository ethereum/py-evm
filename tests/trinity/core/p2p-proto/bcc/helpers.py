from cancel_token import CancelToken

from eth.db.atomic import AtomicDB
from eth.beacon.db.chain import BeaconChainDB
from eth.beacon.types.blocks import BaseBeaconBlock
from eth.constants import (
    ZERO_HASH32,
)

from trinity.protocol.bcc.context import BeaconContext
from trinity.protocol.bcc.peer import (
    BCCPeerFactory,
)

from p2p import ecies
from p2p.tools.paragon.helpers import (
    get_directly_linked_peers_without_handshake as _get_directly_linked_peers_without_handshake,
    get_directly_linked_peers as _get_directly_linked_peers,
)


def get_fresh_chain_db():
    db = AtomicDB()
    genesis_block = BaseBeaconBlock(
        slot=0,
        randao_reveal=ZERO_HASH32,
        candidate_pow_receipt_root=ZERO_HASH32,
        ancestor_hashes=[ZERO_HASH32] * 32,
        state_root=ZERO_HASH32,  # note: not the actual genesis state root
        attestations=[],
        specials=[],
        proposer_signature=None,
    )

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
