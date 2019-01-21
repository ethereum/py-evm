import pytest

import asyncio

from eth2.beacon.types.blocks import BeaconBlock

from trinity.protocol.bcc.servers import BCCRequestServer

from trinity.sync.beacon.chain import BeaconChainSyncer

from .helpers import (
    get_directly_linked_peers_in_peer_pools,
    get_chain_db,
    create_test_block,
    create_branch,
)


async def get_sync_setup(request, event_loop, alice_chain_db, bob_chain_db):
    alice, alice_peer_pool, bob, bob_peer_pool = await get_directly_linked_peers_in_peer_pools(
        request,
        event_loop,
        alice_chain_db=alice_chain_db,
        bob_chain_db=bob_chain_db,
    )

    bob_request_server = BCCRequestServer(bob.context.chain_db, bob_peer_pool)
    alice_syncer = BeaconChainSyncer(alice_chain_db, alice_peer_pool)

    asyncio.ensure_future(bob_request_server.run())
    asyncio.ensure_future(alice_syncer.run())

    def finalizer():
        event_loop.run_until_complete(alice_syncer.cancel())
        event_loop.run_until_complete(bob_request_server.cancel())

    request.addfinalizer(finalizer)
    return alice_syncer


@pytest.mark.asyncio
async def test_sync_from_genesis(request, event_loop):
    genesis = create_test_block(slot=0)
    bob_blocks = (genesis,) + create_branch(length=99, root=genesis)
    alice_chain_db = get_chain_db((genesis,))
    bob_chain_db = get_chain_db(bob_blocks)

    alice_syncer = await get_sync_setup(request, event_loop, alice_chain_db, bob_chain_db)

    await alice_syncer.events.finished.wait()

    assert alice_chain_db.get_canonical_head(BeaconBlock).slot == 99
    assert (alice_chain_db.get_canonical_head(BeaconBlock) ==
            bob_chain_db.get_canonical_head(BeaconBlock))
    for slot in range(100):
        alice_block = alice_chain_db.get_canonical_block_by_slot(slot, BeaconBlock)
        bob_block = bob_chain_db.get_canonical_block_by_slot(slot, BeaconBlock)
        assert alice_block == bob_block


@pytest.mark.asyncio
async def test_sync_from_old_head(request, event_loop):
    genesis = create_test_block(slot=0)
    alice_blocks = (genesis,) + create_branch(length=49, root=genesis)
    bob_blocks = alice_blocks + create_branch(length=50, root=alice_blocks[-1])
    alice_chain_db = get_chain_db(alice_blocks)
    bob_chain_db = get_chain_db(bob_blocks)

    alice_syncer = await get_sync_setup(request, event_loop, alice_chain_db, bob_chain_db)

    await alice_syncer.events.finished.wait()

    assert alice_chain_db.get_canonical_head(BeaconBlock).slot == 99
    assert (alice_chain_db.get_canonical_head(BeaconBlock) ==
            bob_chain_db.get_canonical_head(BeaconBlock))
    for slot in range(100):
        alice_block = alice_chain_db.get_canonical_block_by_slot(slot, BeaconBlock)
        bob_block = bob_chain_db.get_canonical_block_by_slot(slot, BeaconBlock)
        assert alice_block == bob_block


@pytest.mark.asyncio
async def test_reorg_sync(request, event_loop):
    genesis = create_test_block(slot=0)
    alice_blocks = (genesis,) + create_branch(length=49, root=genesis, state_root=b"\x11" * 32)
    bob_blocks = (genesis,) + create_branch(length=99, root=genesis, state_root=b"\x22" * 32)
    alice_chain_db = get_chain_db(alice_blocks)
    bob_chain_db = get_chain_db(bob_blocks)

    alice_syncer = await get_sync_setup(request, event_loop, alice_chain_db, bob_chain_db)

    await alice_syncer.events.finished.wait()

    assert alice_chain_db.get_canonical_head(BeaconBlock).slot == 99
    assert (alice_chain_db.get_canonical_head(BeaconBlock) ==
            bob_chain_db.get_canonical_head(BeaconBlock))
    for slot in range(100):
        alice_block = alice_chain_db.get_canonical_block_by_slot(slot, BeaconBlock)
        bob_block = bob_chain_db.get_canonical_block_by_slot(slot, BeaconBlock)
        assert alice_block == bob_block


@pytest.mark.asyncio
async def test_sync_when_already_at_best_head(request, event_loop):
    genesis = create_test_block(slot=0)
    alice_blocks = (genesis,) + create_branch(length=99, root=genesis, state_root=b"\x11" * 32)
    bob_blocks = (genesis,) + create_branch(length=50, root=genesis, state_root=b"\x22" * 32)
    alice_chain_db = get_chain_db(alice_blocks)
    bob_chain_db = get_chain_db(bob_blocks)

    alice_syncer = await get_sync_setup(request, event_loop, alice_chain_db, bob_chain_db)

    await alice_syncer.events.finished.wait()

    assert alice_chain_db.get_canonical_head(BeaconBlock).slot == 99
    assert alice_chain_db.get_canonical_head(BeaconBlock) == alice_blocks[-1]
    for slot in range(100):
        alice_block = alice_chain_db.get_canonical_block_by_slot(slot, BeaconBlock)
        assert alice_block == alice_blocks[slot]
