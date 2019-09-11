import asyncio

from async_generator import asynccontextmanager
import pytest

from trinity.tools.bcc_factories import (
    AsyncBeaconChainDBFactory,
    BeaconBlockFactory,
    BeaconChainSyncerFactory,
    ConnectionPairFactory,
)


@asynccontextmanager
async def get_sync_setup(request, event_loop, event_bus, alice_branch, bob_branch):
    alice_chaindb = AsyncBeaconChainDBFactory(blocks=alice_branch)
    bob_chaindb = AsyncBeaconChainDBFactory(blocks=bob_branch)
    peer_pair = ConnectionPairFactory(
        alice_chaindb=alice_chaindb, bob_chaindb=bob_chaindb
    )
    async with peer_pair as (alice, bob):

        alice_syncer = BeaconChainSyncerFactory(
            chain_db__db=alice.chain.chaindb.db, peer_pool=alice.handshaked_peers
        )
        asyncio.ensure_future(alice_syncer.run())

        def finalizer():
            event_loop.run_until_complete(alice_syncer.cancel())

        request.addfinalizer(finalizer)
        await alice_syncer.events.finished.wait()
        yield alice, bob


def assert_synced(alice, bob, correct_branch):
    alice_head = alice.chain.get_canonical_head()
    bob_head = bob.chain.get_canonical_head()
    assert alice_head == correct_branch[-1]
    assert alice_head == bob_head
    for correct_block in correct_branch:
        slot = correct_block.slot
        alice_block = alice.chain.get_canonical_block_by_slot(slot)
        bob_block = bob.chain.get_canonical_block_by_slot(slot)
        assert alice_block == bob_block
        assert alice_block == correct_block


@pytest.mark.asyncio
async def test_sync_from_genesis(request, event_loop, event_bus):
    genesis = BeaconBlockFactory()
    alice_branch = (genesis,) + BeaconBlockFactory.create_branch(length=0, root=genesis)
    bob_branch = (genesis,) + BeaconBlockFactory.create_branch(length=99, root=genesis)

    async with get_sync_setup(
        request, event_loop, event_bus, alice_branch, bob_branch
    ) as (alice, bob):
        assert_synced(alice, bob, bob_branch)


@pytest.mark.asyncio
async def test_sync_from_old_head(request, event_loop, event_bus):
    genesis = BeaconBlockFactory()
    alice_branch = (genesis,) + BeaconBlockFactory.create_branch(
        length=49, root=genesis
    )
    bob_branch = alice_branch + BeaconBlockFactory.create_branch(
        length=50, root=alice_branch[-1]
    )
    async with get_sync_setup(
        request, event_loop, event_bus, alice_branch, bob_branch
    ) as (alice, bob):
        assert_synced(alice, bob, bob_branch)


@pytest.mark.asyncio
async def test_reorg_sync(request, event_loop, event_bus):
    genesis = BeaconBlockFactory()
    alice_branch = (genesis,) + BeaconBlockFactory.create_branch(
        length=49, root=genesis, state_root=b"\x11" * 32
    )
    bob_branch = (genesis,) + BeaconBlockFactory.create_branch(
        length=99, root=genesis, state_root=b"\x22" * 32
    )

    async with get_sync_setup(
        request, event_loop, event_bus, alice_branch, bob_branch
    ) as (alice, bob):
        assert_synced(alice, bob, bob_branch)


@pytest.mark.asyncio
async def test_sync_when_already_at_best_head(request, event_loop, event_bus):
    genesis = BeaconBlockFactory()
    alice_branch = (genesis,) + BeaconBlockFactory.create_branch(
        length=99, root=genesis, state_root=b"\x11" * 32
    )
    bob_branch = (genesis,) + BeaconBlockFactory.create_branch(
        length=50, root=genesis, state_root=b"\x22" * 32
    )

    async with get_sync_setup(
        request, event_loop, event_bus, alice_branch, bob_branch
    ) as (alice, bob):
        alice_head = alice.chain.get_canonical_head()
        assert alice_head.slot == 99
        for correct_block in alice_branch:
            slot = correct_block.slot
            alice_block = alice.chain.get_canonical_block_by_slot(slot)
            assert alice_block == correct_block
