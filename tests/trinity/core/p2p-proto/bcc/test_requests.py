import pytest

import asyncio

from p2p.peer import (
    MsgBuffer,
)
from trinity.protocol.bcc.servers import BCCRequestServer
from trinity.protocol.bcc.commands import (
    BeaconBlocks,
)

from .helpers import (
    get_fresh_chain_db,
    create_branch,
    get_directly_linked_peers_in_peer_pools,
)


async def get_request_server_setup(request, event_loop, chain_db):
    alice, alice_peer_pool, bob, bob_peer_pool = await get_directly_linked_peers_in_peer_pools(
        request,
        event_loop,
        chain_db=chain_db,
    )

    response_buffer = MsgBuffer()
    alice.add_subscriber(response_buffer)

    bob_request_server = BCCRequestServer(bob.context.chain_db, bob_peer_pool)
    asyncio.ensure_future(bob_request_server.run())

    def finalizer():
        event_loop.run_until_complete(bob_request_server.cancel())

    return alice, response_buffer


@pytest.mark.asyncio
async def test_get_single_block_by_slot(request, event_loop):
    chain_db = get_fresh_chain_db()
    alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

    block_hash = chain_db.get_canonical_block_hash(0)
    alice.sub_proto.send_get_blocks(block_hash, 1)
    response = await response_buffer.msg_queue.get()

    assert isinstance(response.command, BeaconBlocks)
    assert response.payload == (chain_db.get_block_by_hash(block_hash),)


@pytest.mark.asyncio
async def test_get_single_block_by_hash(request, event_loop):
    chain_db = get_fresh_chain_db()
    alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

    alice.sub_proto.send_get_blocks(0, 1)
    response = await response_buffer.msg_queue.get()

    assert isinstance(response.command, BeaconBlocks)
    assert response.payload == (chain_db.get_canonical_block_by_slot(0),)


@pytest.mark.asyncio
async def test_get_no_blocks(request, event_loop):
    chain_db = get_fresh_chain_db()
    alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

    alice.sub_proto.send_get_blocks(0, 0)
    response = await response_buffer.msg_queue.get()

    assert isinstance(response.command, BeaconBlocks)
    assert len(response.payload) == 0


@pytest.mark.asyncio
async def test_get_unknown_block_by_slot(request, event_loop):
    chain_db = get_fresh_chain_db()
    alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

    alice.sub_proto.send_get_blocks(100, 1)
    response = await response_buffer.msg_queue.get()

    assert isinstance(response.command, BeaconBlocks)
    assert len(response.payload) == 0


@pytest.mark.asyncio
async def test_get_unknown_block_by_hash(request, event_loop):
    chain_db = get_fresh_chain_db()
    alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

    alice.sub_proto.send_get_blocks(b"\x00" * 32, 1)
    response = await response_buffer.msg_queue.get()

    assert isinstance(response.command, BeaconBlocks)
    assert len(response.payload) == 0


@pytest.mark.asyncio
async def test_get_canonical_block_range_by_slot(request, event_loop):
    chain_db = get_fresh_chain_db()
    base_branch = create_branch(3, root=chain_db.get_canonical_block_by_slot(0))
    non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
    canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)
    for branch in [base_branch, non_canonical_branch, canonical_branch]:
        chain_db.persist_block_chain(branch)

    alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

    alice.sub_proto.send_get_blocks(2, 4)
    response = await response_buffer.msg_queue.get()

    assert isinstance(response.command, BeaconBlocks)
    assert len(response.payload) == 4
    assert [block.slot for block in response.payload] == [2, 3, 4, 5]
    assert response.payload == base_branch[1:] + canonical_branch[:2]


@pytest.mark.asyncio
async def test_get_canonical_block_range_by_hash(request, event_loop):
    chain_db = get_fresh_chain_db()
    base_branch = create_branch(3, root=chain_db.get_canonical_block_by_slot(0))
    non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
    canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)
    for branch in [base_branch, non_canonical_branch, canonical_branch]:
        chain_db.persist_block_chain(branch)

    alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

    alice.sub_proto.send_get_blocks(base_branch[1].hash, 4)
    response = await response_buffer.msg_queue.get()

    assert isinstance(response.command, BeaconBlocks)
    assert len(response.payload) == 4
    assert [block.slot for block in response.payload] == [2, 3, 4, 5]
    assert response.payload == base_branch[1:] + canonical_branch[:2]


@pytest.mark.asyncio
async def test_get_incomplete_canonical_block_range(request, event_loop):
    chain_db = get_fresh_chain_db()
    base_branch = create_branch(3, root=chain_db.get_canonical_block_by_slot(0))
    non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
    canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)
    for branch in [base_branch, non_canonical_branch, canonical_branch]:
        chain_db.persist_block_chain(branch)

    alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

    alice.sub_proto.send_get_blocks(3, 10)
    response = await response_buffer.msg_queue.get()

    assert isinstance(response.command, BeaconBlocks)
    assert len(response.payload) == 5
    assert [block.slot for block in response.payload] == [3, 4, 5, 6, 7]
    assert response.payload == base_branch[-1:] + canonical_branch


@pytest.mark.asyncio
async def test_get_non_canonical_branch(request, event_loop):
    chain_db = get_fresh_chain_db()
    base_branch = create_branch(3, root=chain_db.get_canonical_block_by_slot(0))
    non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
    canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)
    for branch in [base_branch, non_canonical_branch, canonical_branch]:
        chain_db.persist_block_chain(branch)

    alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

    alice.sub_proto.send_get_blocks(non_canonical_branch[1].hash, 3)
    response = await response_buffer.msg_queue.get()

    assert isinstance(response.command, BeaconBlocks)
    assert len(response.payload) == 1
    assert [block.slot for block in response.payload] == [5]
    assert response.payload == (non_canonical_branch[1],)
