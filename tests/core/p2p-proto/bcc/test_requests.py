import pytest

import asyncio

from async_generator import asynccontextmanager
import ssz

from p2p.peer import (
    MsgBuffer,
)

from eth2.beacon.types.blocks import (
    BeaconBlock,
)

from trinity.constants import TO_NETWORKING_BROADCAST_CONFIG

from trinity.protocol.bcc.commands import (
    BeaconBlocks,
)
from trinity.protocol.bcc.events import GetBeaconBlocksEvent
from trinity.protocol.bcc.servers import BCCRequestServer
from trinity.protocol.bcc.peer import BCCPeerPoolEventServer

from tests.core.integration_test_helpers import (
    run_peer_pool_event_server,
)

from .helpers import (
    get_chain_db,
    create_test_block,
    create_branch,
    get_directly_linked_peers_in_peer_pools,
)
from eth2.beacon.fork_choice import higher_slot_scoring
from eth2.beacon.state_machines.forks.serenity import SERENITY_CONFIG


@asynccontextmanager
async def get_request_server_setup(request, event_loop, event_bus, chain_db):
    genesis = await chain_db.coro_get_canonical_block_by_slot(
        SERENITY_CONFIG.GENESIS_SLOT,
        BeaconBlock,
    )
    alice_chain_db = await get_chain_db((genesis,))
    alice, alice_peer_pool, bob, bob_peer_pool = await get_directly_linked_peers_in_peer_pools(
        request,
        event_loop,
        alice_chain_db=alice_chain_db,
        bob_chain_db=chain_db,
        bob_peer_pool_event_bus=event_bus,
    )

    response_buffer = MsgBuffer()
    alice.add_subscriber(response_buffer)

    async with run_peer_pool_event_server(
        event_bus, bob_peer_pool, handler_type=BCCPeerPoolEventServer
    ):

        bob_request_server = BCCRequestServer(
            event_bus, TO_NETWORKING_BROADCAST_CONFIG, bob.context.chain_db)
        asyncio.ensure_future(bob_request_server.run())

        await event_bus.wait_until_all_endpoints_subscribed_to(GetBeaconBlocksEvent)

        def finalizer():
            event_loop.run_until_complete(bob_request_server.cancel())

        request.addfinalizer(finalizer)

        yield alice, response_buffer


@pytest.mark.asyncio
async def test_get_single_block_by_slot(request, event_loop, event_bus):
    block = create_test_block()
    chain_db = await get_chain_db((block,))
    async with get_request_server_setup(
        request, event_loop, event_bus, chain_db
    ) as (alice, response_buffer):

        alice.sub_proto.send_get_blocks(block.signing_root, 1, request_id=5)
        response = await response_buffer.msg_queue.get()

        assert isinstance(response.command, BeaconBlocks)
        assert response.payload == {
            "request_id": 5,
            "encoded_blocks": (ssz.encode(block),),
        }


@pytest.mark.asyncio
async def test_get_single_block_by_root(request, event_loop, event_bus):
    block = create_test_block()
    chain_db = await get_chain_db((block,))
    async with get_request_server_setup(
        request, event_loop, event_bus, chain_db
    ) as (alice, response_buffer):

        alice.sub_proto.send_get_blocks(block.slot, 1, request_id=5)
        response = await response_buffer.msg_queue.get()

        assert isinstance(response.command, BeaconBlocks)
        assert response.payload == {
            "request_id": 5,
            "encoded_blocks": (ssz.encode(block),),
        }


@pytest.mark.asyncio
async def test_get_no_blocks(request, event_loop, event_bus):
    block = create_test_block()
    chain_db = await get_chain_db((block,))
    async with get_request_server_setup(
        request, event_loop, event_bus, chain_db
    ) as (alice, response_buffer):

        alice.sub_proto.send_get_blocks(block.slot, 0, request_id=5)
        response = await response_buffer.msg_queue.get()

        assert isinstance(response.command, BeaconBlocks)
        assert response.payload == {
            "request_id": 5,
            "encoded_blocks": (),
        }


@pytest.mark.asyncio
async def test_get_unknown_block_by_slot(request, event_loop, event_bus):
    block = create_test_block()
    chain_db = await get_chain_db((block,))
    async with get_request_server_setup(
        request, event_loop, event_bus, chain_db
    ) as (alice, response_buffer):

        alice.sub_proto.send_get_blocks(block.slot + 100, 1, request_id=5)
        response = await response_buffer.msg_queue.get()

        assert isinstance(response.command, BeaconBlocks)
        assert response.payload == {
            "request_id": 5,
            "encoded_blocks": (),
        }


@pytest.mark.asyncio
async def test_get_unknown_block_by_root(request, event_loop, event_bus):
    block = create_test_block()
    chain_db = await get_chain_db((block,))
    async with get_request_server_setup(
        request, event_loop, event_bus, chain_db
    ) as (alice, response_buffer):

        alice.sub_proto.send_get_blocks(b"\x00" * 32, 1, request_id=5)
        response = await response_buffer.msg_queue.get()

        assert isinstance(response.command, BeaconBlocks)
        assert response.payload == {
            "request_id": 5,
            "encoded_blocks": (),
        }


@pytest.mark.asyncio
async def test_get_canonical_block_range_by_slot(request, event_loop, event_bus):
    chain_db = await get_chain_db()

    genesis = create_test_block()
    base_branch = create_branch(3, root=genesis)
    non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)

    canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)

    for branch in [[genesis], base_branch, non_canonical_branch, canonical_branch]:
        scorings = (higher_slot_scoring for block in branch)
        await chain_db.coro_persist_block_chain(branch, BeaconBlock, scorings)

    async with get_request_server_setup(
        request, event_loop, event_bus, chain_db
    ) as (alice, response_buffer):

        alice.sub_proto.send_get_blocks(genesis.slot + 2, 4, request_id=5)
        response = await response_buffer.msg_queue.get()

        assert isinstance(response.command, BeaconBlocks)
        assert response.payload["request_id"] == 5
        blocks = tuple(
            ssz.decode(block, BeaconBlock) for block in response.payload["encoded_blocks"])
        assert len(blocks) == 4
        assert [block.slot for block in blocks] == [genesis.slot + s for s in [2, 3, 4, 5]]
        assert blocks == base_branch[1:] + canonical_branch[:2]


@pytest.mark.asyncio
async def test_get_canonical_block_range_by_root(request, event_loop, event_bus):
    chain_db = await get_chain_db()

    genesis = create_test_block()
    base_branch = create_branch(3, root=genesis)
    non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
    canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)

    for branch in [[genesis], base_branch, non_canonical_branch, canonical_branch]:
        scorings = (higher_slot_scoring for block in branch)
        await chain_db.coro_persist_block_chain(branch, BeaconBlock, scorings)

    async with get_request_server_setup(
        request, event_loop, event_bus, chain_db
    ) as (alice, response_buffer):

        alice.sub_proto.send_get_blocks(base_branch[1].signing_root, 4, request_id=5)
        response = await response_buffer.msg_queue.get()

        assert isinstance(response.command, BeaconBlocks)
        assert response.payload["request_id"] == 5
        blocks = tuple(
            ssz.decode(block, BeaconBlock) for block in response.payload["encoded_blocks"])
        assert len(blocks) == 4
        assert [block.slot for block in blocks] == [genesis.slot + s for s in [2, 3, 4, 5]]
        assert blocks == base_branch[1:] + canonical_branch[:2]


@pytest.mark.asyncio
async def test_get_incomplete_canonical_block_range(request, event_loop, event_bus):
    chain_db = await get_chain_db()

    genesis = create_test_block()
    base_branch = create_branch(3, root=genesis)
    non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
    canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)

    for branch in [[genesis], base_branch, non_canonical_branch, canonical_branch]:
        scorings = (higher_slot_scoring for block in branch)
        await chain_db.coro_persist_block_chain(branch, BeaconBlock, scorings)

    async with get_request_server_setup(
        request, event_loop, event_bus, chain_db
    ) as (alice, response_buffer):

        alice.sub_proto.send_get_blocks(genesis.slot + 3, 10, request_id=5)
        response = await response_buffer.msg_queue.get()

        assert isinstance(response.command, BeaconBlocks)
        assert response.payload["request_id"] == 5
        blocks = tuple(
            ssz.decode(block, BeaconBlock) for block in response.payload["encoded_blocks"])
        assert len(blocks) == 5
        assert [block.slot for block in blocks] == [genesis.slot + s for s in [3, 4, 5, 6, 7]]
        assert blocks == base_branch[-1:] + canonical_branch


@pytest.mark.asyncio
async def test_get_non_canonical_branch(request, event_loop, event_bus):
    chain_db = await get_chain_db()

    genesis = create_test_block()
    base_branch = create_branch(3, root=genesis)
    non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
    canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)

    for branch in [[genesis], base_branch, non_canonical_branch, canonical_branch]:
        scorings = (higher_slot_scoring for block in branch)
        await chain_db.coro_persist_block_chain(branch, BeaconBlock, scorings)

    async with get_request_server_setup(
        request, event_loop, event_bus, chain_db
    ) as (alice, response_buffer):

        alice.sub_proto.send_get_blocks(non_canonical_branch[1].signing_root, 3, request_id=5)
        response = await response_buffer.msg_queue.get()

        assert isinstance(response.command, BeaconBlocks)
        assert response.payload["request_id"] == 5
        blocks = tuple(
            ssz.decode(block, BeaconBlock) for block in response.payload["encoded_blocks"])
        assert len(blocks) == 1
        assert blocks[0].slot == genesis.slot + 5
        assert blocks[0] == non_canonical_branch[1]
