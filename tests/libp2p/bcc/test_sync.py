import pytest

import asyncio


from async_generator import asynccontextmanager
from eth2.beacon.fork_choice.higher_slot import higher_slot_scoring
from eth2.beacon.types.blocks import BeaconBlock

from trinity.constants import TO_NETWORKING_BROADCAST_CONFIG
from trinity.protocol.bcc.peer import BCCPeerPoolEventServer

from trinity.sync.beacon.chain import BeaconChainSyncer

from trinity.tools.bcc_factories import (
    BCCPeerPairFactory,
    BCCPeerPoolFactory,
    BeaconContextFactory,
    BeaconChainSyncerFactory,
    AsyncBeaconChainDBFactory,
    ConnectionPairFactory,
    BeaconBlockFactory,
)

from tests.core.integration_test_helpers import run_peer_pool_event_server


def create_test_block():
    return BeaconBlockFactory()


def create_branch(length, root=None, **start_kwargs):
    return BeaconBlockFactory.create_branch(length, root, **start_kwargs)


async def get_chain_db(blocks=()):
    return AsyncBeaconChainDBFactory(blocks=blocks)


@asynccontextmanager
async def get_sync_setup(
    request, event_loop, event_bus, alice_best_slot, bob_best_slot
):
    peer_pair = ConnectionPairFactory(
        alice_best_slot=alice_best_slot, bob_best_slot=bob_best_slot
    )
    async with peer_pair as (alice, bob):

        alice_syncer = BeaconChainSyncerFactory(
            chain_db__db=alice.chain.chaindb.db,
            peer_pool=alice.handshaked_peers)
        asyncio.ensure_future(alice_syncer.run())

        def finalizer():
            event_loop.run_until_complete(alice_syncer.cancel())

        request.addfinalizer(finalizer)
        await alice_syncer.events.finished.wait()
        yield alice_syncer, alice, bob


from eth2.beacon.tools.factories import BeaconChainFactory, genesis_state, genesis_block
from eth2.beacon.chains.testnet import TestnetChain
from trinity.tools.bcc_factories import NodeFactory

from eth2.configs import Eth2GenesisConfig


@pytest.mark.asyncio
async def test_foo(request, event_loop, event_bus):
    bob = NodeFactory(chain__best_slot=99)
    assert bob.chain.chaindb.get_canonical_head(BeaconBlock).slot == 99


@pytest.mark.asyncio
async def test_sync_from_genesis(request, event_loop, event_bus):

    async with get_sync_setup(
        request, event_loop, event_bus, alice_best_slot=0, bob_best_slot=99
    ) as (alice_syncer, alice, bob):

        alice_head = alice.chain.get_canonical_head()
        bob_head = bob.chain.get_canonical_head()
        assert alice_head.slot ==  99
        assert alice_head == bob_head
        for slot in range(100):
            alice_block = await alice.chain.get_canonical_block_by_slot(slot)
            bob_block = await alice.chain.get_canonical_block_by_slot(slot)
            assert alice_block == bob_block


@pytest.mark.asyncio
async def test_sync_from_old_head(request, event_loop, event_bus):
    genesis = create_test_block()
    alice_blocks = (genesis,) + create_branch(length=49, root=genesis)
    bob_blocks = alice_blocks + create_branch(length=50, root=alice_blocks[-1])
    alice_chain_db = await get_chain_db(alice_blocks)
    bob_chain_db = await get_chain_db(bob_blocks)

    async with get_sync_setup(
        request, event_loop, event_bus, alice_chain_db, bob_chain_db
    ):

        alice_head = await alice_chain_db.coro_get_canonical_head(BeaconBlock)
        bob_head = await bob_chain_db.coro_get_canonical_head(BeaconBlock)

        assert alice_head.slot == genesis.slot + 99
        assert alice_head == bob_head
        for slot in range(genesis.slot, genesis.slot + 100):
            alice_block = await alice_chain_db.coro_get_canonical_block_by_slot(
                slot, BeaconBlock
            )
            bob_block = await bob_chain_db.coro_get_canonical_block_by_slot(
                slot, BeaconBlock
            )
            assert alice_block == bob_block


@pytest.mark.asyncio
async def test_reorg_sync(request, event_loop, event_bus):
    genesis = create_test_block()
    alice_blocks = (genesis,) + create_branch(
        length=49, root=genesis, state_root=b"\x11" * 32
    )
    bob_blocks = (genesis,) + create_branch(
        length=99, root=genesis, state_root=b"\x22" * 32
    )
    alice_chain_db = await get_chain_db(alice_blocks)
    bob_chain_db = await get_chain_db(bob_blocks)

    async with get_sync_setup(
        request, event_loop, event_bus, alice_chain_db, bob_chain_db
    ):

        alice_head = await alice_chain_db.coro_get_canonical_head(BeaconBlock)
        bob_head = await bob_chain_db.coro_get_canonical_head(BeaconBlock)

        assert alice_head.slot == genesis.slot + 99
        assert alice_head == bob_head
        for slot in range(genesis.slot, genesis.slot + 100):
            alice_block = await alice_chain_db.coro_get_canonical_block_by_slot(
                slot, BeaconBlock
            )
            bob_block = await bob_chain_db.coro_get_canonical_block_by_slot(
                slot, BeaconBlock
            )
            assert alice_block == bob_block


@pytest.mark.asyncio
async def test_sync_when_already_at_best_head(request, event_loop, event_bus):
    genesis = create_test_block()
    alice_blocks = (genesis,) + create_branch(
        length=99, root=genesis, state_root=b"\x11" * 32
    )
    bob_blocks = (genesis,) + create_branch(
        length=50, root=genesis, state_root=b"\x22" * 32
    )
    alice_chain_db = await get_chain_db(alice_blocks)
    bob_chain_db = await get_chain_db(bob_blocks)

    async with get_sync_setup(
        request, event_loop, event_bus, alice_chain_db, bob_chain_db
    ):

        alice_head = await alice_chain_db.coro_get_canonical_head(BeaconBlock)

        assert alice_head.slot == genesis.slot + 99
        assert alice_head == alice_blocks[-1]
        for slot in range(genesis.slot, genesis.slot + 100):
            alice_block = await alice_chain_db.coro_get_canonical_block_by_slot(
                slot, BeaconBlock
            )
            assert alice_block == alice_blocks[slot - genesis.slot]
