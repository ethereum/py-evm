import asyncio

from async_generator import asynccontextmanager
import pytest

from trinity.tools.bcc_factories import (
    BeaconChainSyncerFactory,
    ConnectionPairFactory,
)


@asynccontextmanager
async def get_sync_setup(
    request, event_loop, event_bus, alice_best_slot, bob_best_slot
):
    peer_pair = ConnectionPairFactory(
        alice_best_slot=alice_best_slot, bob_best_slot=bob_best_slot
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
        yield alice_syncer, alice, bob


@pytest.mark.asyncio
async def test_sync_from_genesis(request, event_loop, event_bus):

    async with get_sync_setup(
        request, event_loop, event_bus, alice_best_slot=0, bob_best_slot=99
    ) as (alice_syncer, alice, bob):

        alice_head = alice.chain.get_canonical_head()
        bob_head = bob.chain.get_canonical_head()
        assert alice_head.slot == 99
        assert alice_head == bob_head
        for slot in range(100):
            alice_block = alice.chain.get_canonical_block_by_slot(slot)
            bob_block = alice.chain.get_canonical_block_by_slot(slot)
            assert alice_block == bob_block
