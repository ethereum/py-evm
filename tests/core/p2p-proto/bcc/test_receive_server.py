import asyncio

from typing import (
    Tuple,
)

import pytest

import ssz

from p2p.peer import (
    MsgBuffer,
)

from eth2.beacon.chains.base import (
    BeaconChain,
)
from eth2.beacon.types.blocks import (
    BeaconBlock,
)

from trinity.protocol.bcc.peer import (
    BCCPeer,
)
from trinity.protocol.bcc.servers import (
    BCCReceiveServer,
)
from trinity.protocol.bcc.commands import (
    BeaconBlocks,
)

from .helpers import (
    get_genesis_chain_db,
    create_test_block,
    get_directly_linked_peers_in_peer_pools,
)


async def get_peer_and_receive_server(request, event_loop) -> Tuple[BCCPeer, BCCReceiveServer]:
    alice_chain_db = await get_genesis_chain_db()
    bob_chain_db = await get_genesis_chain_db()
    alice, alice_peer_pool, bob, bob_peer_pool = await get_directly_linked_peers_in_peer_pools(
        request,
        event_loop,
        alice_chain_db=alice_chain_db,
        bob_chain_db=bob_chain_db,
    )

    chain = BeaconChain(bob_chain_db.db)
    bob_receive_server = BCCReceiveServer(chain=chain, peer_pool=bob_peer_pool)
    asyncio.ensure_future(bob_receive_server.run())

    def finalizer():
        event_loop.run_until_complete(bob_receive_server.cancel())

    request.addfinalizer(finalizer)

    return alice, bob_receive_server


@pytest.mark.asyncio
async def test_send_block(request, event_loop):
    alice, bob_receive_server = await get_peer_and_receive_server(request, event_loop)


# @pytest.mark.asyncio
# async def test_get_single_block_by_root(request, event_loop):
#     block = create_test_block()
#     chain_db = await get_chain_db((block,))
#     alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

#     alice.sub_proto.send_get_blocks(block.slot, 1, request_id=5)
#     response = await response_buffer.msg_queue.get()

#     assert isinstance(response.command, BeaconBlocks)
#     assert response.payload == {
#         "request_id": 5,
#         "encoded_blocks": (ssz.encode(block),),
#     }


# @pytest.mark.asyncio
# async def test_get_no_blocks(request, event_loop):
#     block = create_test_block()
#     chain_db = await get_chain_db((block,))
#     alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

#     alice.sub_proto.send_get_blocks(block.slot, 0, request_id=5)
#     response = await response_buffer.msg_queue.get()

#     assert isinstance(response.command, BeaconBlocks)
#     assert response.payload == {
#         "request_id": 5,
#         "encoded_blocks": (),
#     }


# @pytest.mark.asyncio
# async def test_get_unknown_block_by_slot(request, event_loop):
#     block = create_test_block()
#     chain_db = await get_chain_db((block,))
#     alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

#     alice.sub_proto.send_get_blocks(block.slot + 100, 1, request_id=5)
#     response = await response_buffer.msg_queue.get()

#     assert isinstance(response.command, BeaconBlocks)
#     assert response.payload == {
#         "request_id": 5,
#         "encoded_blocks": (),
#     }


# @pytest.mark.asyncio
# async def test_get_unknown_block_by_root(request, event_loop):
#     block = create_test_block()
#     chain_db = await get_chain_db((block,))
#     alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

#     alice.sub_proto.send_get_blocks(b"\x00" * 32, 1, request_id=5)
#     response = await response_buffer.msg_queue.get()

#     assert isinstance(response.command, BeaconBlocks)
#     assert response.payload == {
#         "request_id": 5,
#         "encoded_blocks": (),
#     }


# @pytest.mark.asyncio
# async def test_get_canonical_block_range_by_slot(request, event_loop):
#     chain_db = await get_chain_db()

#     genesis = create_test_block()
#     base_branch = create_branch(3, root=genesis)
#     non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)

#     canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)

#     for branch in [[genesis], base_branch, non_canonical_branch, canonical_branch]:
#         await chain_db.coro_persist_block_chain(branch, BeaconBlock)

#     alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

#     alice.sub_proto.send_get_blocks(genesis.slot + 2, 4, request_id=5)
#     response = await response_buffer.msg_queue.get()

#     assert isinstance(response.command, BeaconBlocks)
#     assert response.payload["request_id"] == 5
#     blocks = tuple(ssz.decode(block, BeaconBlock) for block in response.payload["encoded_blocks"])
#     assert len(blocks) == 4
#     assert [block.slot for block in blocks] == [genesis.slot + s for s in [2, 3, 4, 5]]
#     assert blocks == base_branch[1:] + canonical_branch[:2]


# @pytest.mark.asyncio
# async def test_get_canonical_block_range_by_root(request, event_loop):
#     chain_db = await get_chain_db()

#     genesis = create_test_block()
#     base_branch = create_branch(3, root=genesis)
#     non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
#     canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)

#     for branch in [[genesis], base_branch, non_canonical_branch, canonical_branch]:
#         await chain_db.coro_persist_block_chain(branch, BeaconBlock)

#     alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

#     alice.sub_proto.send_get_blocks(base_branch[1].root, 4, request_id=5)
#     response = await response_buffer.msg_queue.get()

#     assert isinstance(response.command, BeaconBlocks)
#     assert response.payload["request_id"] == 5
#     blocks = tuple(ssz.decode(block, BeaconBlock) for block in response.payload["encoded_blocks"])
#     assert len(blocks) == 4
#     assert [block.slot for block in blocks] == [genesis.slot + s for s in [2, 3, 4, 5]]
#     assert blocks == base_branch[1:] + canonical_branch[:2]


# @pytest.mark.asyncio
# async def test_get_incomplete_canonical_block_range(request, event_loop):
#     chain_db = await get_chain_db()

#     genesis = create_test_block()
#     base_branch = create_branch(3, root=genesis)
#     non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
#     canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)

#     for branch in [[genesis], base_branch, non_canonical_branch, canonical_branch]:
#         await chain_db.coro_persist_block_chain(branch, BeaconBlock)

#     alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

#     alice.sub_proto.send_get_blocks(genesis.slot + 3, 10, request_id=5)
#     response = await response_buffer.msg_queue.get()

#     assert isinstance(response.command, BeaconBlocks)
#     assert response.payload["request_id"] == 5
#     blocks = tuple(ssz.decode(block, BeaconBlock) for block in response.payload["encoded_blocks"])
#     assert len(blocks) == 5
#     assert [block.slot for block in blocks] == [genesis.slot + s for s in [3, 4, 5, 6, 7]]
#     assert blocks == base_branch[-1:] + canonical_branch


# @pytest.mark.asyncio
# async def test_get_non_canonical_branch(request, event_loop):
#     chain_db = await get_chain_db()

#     genesis = create_test_block()
#     base_branch = create_branch(3, root=genesis)
#     non_canonical_branch = create_branch(3, root=base_branch[-1], state_root=b"\x00" * 32)
#     canonical_branch = create_branch(4, root=base_branch[-1], state_root=b"\x11" * 32)

#     for branch in [[genesis], base_branch, non_canonical_branch, canonical_branch]:
#         await chain_db.coro_persist_block_chain(branch, BeaconBlock)

#     alice, response_buffer = await get_request_server_setup(request, event_loop, chain_db)

#     alice.sub_proto.send_get_blocks(non_canonical_branch[1].root, 3, request_id=5)
#     response = await response_buffer.msg_queue.get()

#     assert isinstance(response.command, BeaconBlocks)
#     assert response.payload["request_id"] == 5
#     blocks = tuple(ssz.decode(block, BeaconBlock) for block in response.payload["encoded_blocks"])
#     assert len(blocks) == 1
#     assert blocks[0].slot == genesis.slot + 5
#     assert blocks[0] == non_canonical_branch[1]
