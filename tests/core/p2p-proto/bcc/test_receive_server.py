import asyncio
import functools

from typing import (
    Tuple,
)

import pytest

import ssz

from eth_utils import (
    ValidationError,
)

from p2p.peer import (
    MsgBuffer,
)

from eth.exceptions import (
    BlockNotFound,
)

from eth2.beacon.chains.testnet import TestnetChain
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth2.beacon.typing import (
    FromBlockParams,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)

from trinity.protocol.bcc.peer import (
    BCCPeer,
)
from trinity.protocol.bcc.servers import (
    BCCReceiveServer,
    BCCRequestServer,
    OrphanBlockPool,
)

from .helpers import (
    FakeAsyncBeaconChainDB,
    get_genesis_chain_db,
    create_test_block,
    get_directly_linked_peers_in_peer_pools,
)


class FakeChain(TestnetChain):
    chaindb_class = FakeAsyncBeaconChainDB

    def import_block(
            self,
            block: BaseBeaconBlock,
            perform_validation: bool=True) -> Tuple[
                BaseBeaconBlock, Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        """
        Remove the logics about `state`, because we only need to check a block's parent in
        `ReceiveServer`.
        """
        try:
            self.get_block_by_root(block.previous_block_root)
        except BlockNotFound:
            raise ValidationError
        (
            new_canonical_blocks,
            old_canonical_blocks,
        ) = self.chaindb.persist_block(block, block.__class__)
        return block, new_canonical_blocks, old_canonical_blocks


async def get_fake_chain() -> FakeChain:
    chain_db = await get_genesis_chain_db()
    return FakeChain(chain_db.db)


async def get_peer_and_receive_server(request, event_loop) -> Tuple[
        BCCPeer, BCCReceiveServer]:
    alice_chain = await get_fake_chain()
    bob_chain = await get_fake_chain()

    alice, alice_peer_pool, bob, bob_peer_pool = await get_directly_linked_peers_in_peer_pools(
        request,
        event_loop,
        alice_chain_db=alice_chain.chaindb,
        bob_chain_db=bob_chain.chaindb,
    )

    # Add a queue to ensure messages put after every msg handler finishes.
    # This is crucial to synchronize the test with the BCCReceiveServer.
    msg_queue = asyncio.Queue()
    orig_handle_msg = BCCReceiveServer._handle_msg

    async def _handle_msg(self, base_peer, cmd, msg):
        task = asyncio.ensure_future(orig_handle_msg(self, base_peer, cmd, msg))

        def enqueue_msg(future, msg):
            msg_queue.put_nowait(msg)
        task.add_done_callback(functools.partial(enqueue_msg, msg=msg))
        await task
    BCCReceiveServer._handle_msg = _handle_msg

    alice_req_server = BCCRequestServer(
        db=alice_chain.chaindb,
        peer_pool=alice_peer_pool,
    )
    bob_recv_server = BCCReceiveServer(chain=bob_chain, peer_pool=bob_peer_pool)

    asyncio.ensure_future(alice_req_server.run())
    asyncio.ensure_future(bob_recv_server.run())
    await alice_req_server.events.started.wait()
    await bob_recv_server.events.started.wait()

    def finalizer():
        event_loop.run_until_complete(alice_req_server.cancel())
        event_loop.run_until_complete(bob_recv_server.cancel())

    request.addfinalizer(finalizer)

    return alice, alice_req_server, bob_recv_server, msg_queue


def test_orphan_block_pool():
    pool = OrphanBlockPool()
    b0 = create_test_block()
    b1 = create_test_block(parent=b0)
    b2 = create_test_block(parent=b0, state_root=b"\x11" * 32)
    # test: add
    pool.add(b1)
    assert b1 in pool._pool
    # test: add: no side effect for adding twice
    pool.add(b1)
    # test: add: two blocks
    pool.add(b2)
    # test: get
    assert pool.get(b1.signing_root) == b1
    assert pool.get(b2.signing_root) == b2
    # test: pop_children
    b2_children = pool.pop_children(b2)
    assert len(b2_children) == 0
    b0_children = pool.pop_children(b0)
    assert len(b0_children) == 2 and (b1 in b0_children) and (b2 in b0_children)


@pytest.mark.asyncio
async def test_bcc_receive_server_try_import_or_handle_orphan(request, event_loop, monkeypatch):
    _, _, bob_recv_server, _ = await get_peer_and_receive_server(request, event_loop)

    def _request_block_by_root(block_root):
        pass

    monkeypatch.setattr(
        bob_recv_server,
        '_request_block_by_root',
        _request_block_by_root,
    )

    bob_chain = bob_recv_server.chain
    head = bob_chain.get_canonical_head()
    block_0 = bob_chain.create_block_from_parent(
        parent_block=head,
        block_params=FromBlockParams(),
    )
    block_1 = bob_chain.create_block_from_parent(
        parent_block=block_0,
        block_params=FromBlockParams(),
    )
    block_2 = bob_chain.create_block_from_parent(
        parent_block=block_1,
        block_params=FromBlockParams(),
    )
    block_3 = bob_chain.create_block_from_parent(
        parent_block=block_2,
        block_params=FromBlockParams(),
    )
    # test: block should not be in the db before imported.
    assert not bob_recv_server._is_block_root_in_db(block_0.signing_root)
    # test: block with its parent in db should be imported successfully.
    bob_recv_server._try_import_or_handle_orphan(block_0)

    assert bob_recv_server._is_block_root_in_db(block_0.signing_root)
    # test: block without its parent in db should not be imported, and it should be put in the
    #   `orphan_block_pool`.
    bob_recv_server._try_import_or_handle_orphan(block_2)
    assert not bob_recv_server._is_block_root_in_db(block_2.signing_root)
    assert bob_recv_server._is_block_root_in_orphan_block_pool(block_2.signing_root)
    bob_recv_server._try_import_or_handle_orphan(block_3)
    assert not bob_recv_server._is_block_root_in_db(block_3.signing_root)
    assert block_3 in bob_recv_server.orphan_block_pool._pool
    # test: a successfully imported parent is present, its children should be processed
    #   recursively.
    bob_recv_server._try_import_or_handle_orphan(block_1)
    assert bob_recv_server._is_block_root_in_db(block_1.signing_root)
    assert bob_recv_server._is_block_root_in_db(block_2.signing_root)
    assert block_2 not in bob_recv_server.orphan_block_pool._pool
    assert bob_recv_server._is_block_root_in_db(block_3.signing_root)
    assert block_3 not in bob_recv_server.orphan_block_pool._pool


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_beacon_blocks_checks(request, event_loop, monkeypatch):
    alice, _, bob_recv_server, bob_msg_queue = await get_peer_and_receive_server(
        request,
        event_loop,
    )
    bob_chain = bob_recv_server.chain
    head = bob_chain.get_canonical_head()
    block_0 = bob_chain.create_block_from_parent(
        parent_block=head,
        block_params=FromBlockParams(),
    )

    event = asyncio.Event()

    def _try_import_or_handle_orphan(block):
        event.set()

    monkeypatch.setattr(
        bob_recv_server,
        '_try_import_or_handle_orphan',
        _try_import_or_handle_orphan,
    )

    # test: `request_id` not found, it should be rejected
    inexistent_request_id = 5566
    assert inexistent_request_id not in bob_recv_server.map_requested_id_block_root
    alice.sub_proto.send_blocks(blocks=(block_0,), request_id=inexistent_request_id)
    await bob_msg_queue.get()
    assert not event.is_set()

    # test: >= 1 blocks are sent, the request should be rejected.
    event.clear()
    existing_request_id = 1
    bob_recv_server.map_requested_id_block_root[existing_request_id] = block_0.signing_root
    alice.sub_proto.send_blocks(blocks=(block_0, block_0), request_id=existing_request_id)
    await bob_msg_queue.get()
    assert not event.is_set()

    # test: `request_id` is found but `block.signing_root` does not correspond to the request
    event.clear()
    existing_request_id = 2
    bob_recv_server.map_requested_id_block_root[existing_request_id] = b'\x12' * 32
    alice.sub_proto.send_blocks(blocks=(block_0,), request_id=existing_request_id)
    await bob_msg_queue.get()
    assert not event.is_set()

    # test: `request_id` is found and the block is valid. It should be imported.
    event.clear()
    existing_request_id = 3
    bob_recv_server.map_requested_id_block_root[existing_request_id] = block_0.signing_root
    alice.sub_proto.send_blocks(blocks=(block_0,), request_id=existing_request_id)
    await bob_msg_queue.get()
    assert event.is_set()
    # ensure `request_id` is cleared after successful response
    assert existing_request_id not in bob_recv_server.map_requested_id_block_root


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_new_beacon_block_checks(request, event_loop, monkeypatch):
    alice, _, bob_recv_server, bob_msg_queue = await get_peer_and_receive_server(
        request,
        event_loop,
    )
    bob_chain = bob_recv_server.chain
    head = bob_chain.get_canonical_head()
    block_0 = bob_chain.create_block_from_parent(
        parent_block=head,
        block_params=FromBlockParams(),
    )

    event = asyncio.Event()

    def _try_import_or_handle_orphan(block):
        event.set()

    monkeypatch.setattr(
        bob_recv_server,
        '_try_import_or_handle_orphan',
        _try_import_or_handle_orphan,
    )

    alice.sub_proto.send_new_block(block=block_0)
    await bob_msg_queue.get()
    assert event.is_set()

    # test: seen blocks should be rejected
    event.clear()
    bob_recv_server.orphan_block_pool.add(block_0)
    alice.sub_proto.send_new_block(block=block_0)
    await bob_msg_queue.get()
    assert not event.is_set()


def parse_new_block_msg(msg):
    key = "encoded_block"
    assert key in msg
    return ssz.decode(msg[key], SerenityBeaconBlock)


def parse_resp_block_msg(msg):
    key = "encoded_blocks"
    # TODO: remove this condition check in the future, when we start requesting more than one
    #   block at a time in `_handle_beacon_blocks`.
    assert len(msg[key]) == 1
    return ssz.decode(msg[key][0], SerenityBeaconBlock)


@pytest.mark.asyncio
async def test_bcc_receive_request_block_by_root(request, event_loop):
    alice, alice_req_server, bob_recv_server, bob_msg_queue = await get_peer_and_receive_server(
        request,
        event_loop,
    )
    alice_msg_buffer = MsgBuffer()
    alice.add_subscriber(alice_msg_buffer)
    bob_chain = bob_recv_server.chain
    head = bob_chain.get_canonical_head()
    block_0 = bob_chain.create_block_from_parent(
        parent_block=head,
        block_params=FromBlockParams(),
    )

    # test: request from bob is issued and received by alice
    bob_recv_server._request_block_by_root(block_0.signing_root)
    req = await alice_msg_buffer.msg_queue.get()
    assert req.payload['block_slot_or_root'] == block_0.signing_root

    # test: alice responds to the bob's request
    await alice_req_server.db.coro_persist_block(
        block_0,
        SerenityBeaconBlock,
    )
    bob_recv_server._request_block_by_root(block_0.signing_root)
    msg_block = await bob_msg_queue.get()
    assert block_0 == parse_resp_block_msg(msg_block)


@pytest.mark.asyncio
async def test_bcc_receive_server_with_request_server(request, event_loop):
    alice, alice_req_server, bob_recv_server, bob_msg_queue = await get_peer_and_receive_server(
        request,
        event_loop,
    )
    alice_msg_buffer = MsgBuffer()
    alice.add_subscriber(alice_msg_buffer)
    bob_chain = bob_recv_server.chain
    head = bob_chain.get_canonical_head()
    block_0 = bob_chain.create_block_from_parent(
        parent_block=head,
        block_params=FromBlockParams(),
    )
    block_1 = bob_chain.create_block_from_parent(
        parent_block=block_0,
        block_params=FromBlockParams(),
    )
    block_2 = bob_chain.create_block_from_parent(
        parent_block=block_1,
        block_params=FromBlockParams(),
    )
    await alice_req_server.db.coro_persist_block(
        block_0,
        SerenityBeaconBlock,
    )
    await alice_req_server.db.coro_persist_block(
        block_1,
        SerenityBeaconBlock,
    )
    await alice_req_server.db.coro_persist_block(
        block_2,
        SerenityBeaconBlock,
    )

    # test: alice send `block_2` to bob, and bob should be able to get `block_1` and `block_0`
    #   later through the requests.
    assert not bob_recv_server._is_block_seen(block_0)
    assert not bob_recv_server._is_block_seen(block_1)
    assert not bob_recv_server._is_block_seen(block_2)
    alice.sub_proto.send_new_block(block=block_2)
    # bob receives new block `block_2`
    assert block_2 == parse_new_block_msg(await bob_msg_queue.get())
    # bob requests for `block_1`, and alice receives the request
    req_1 = await alice_msg_buffer.msg_queue.get()
    assert req_1.payload['block_slot_or_root'] == block_1.signing_root
    # bob receives the response block `block_1`
    assert block_1 == parse_resp_block_msg(await bob_msg_queue.get())
    # bob requests for `block_0`, and alice receives the request
    req_0 = await alice_msg_buffer.msg_queue.get()
    assert req_0.payload['block_slot_or_root'] == block_0.signing_root
    # bob receives the response block `block_0`
    assert block_0 == parse_resp_block_msg(await bob_msg_queue.get())
    assert bob_recv_server._is_block_root_in_db(block_0.signing_root)
    assert bob_recv_server._is_block_root_in_db(block_1.signing_root)
    assert bob_recv_server._is_block_root_in_db(block_2.signing_root)
