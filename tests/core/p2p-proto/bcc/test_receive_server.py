import asyncio
import time

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
from eth2.beacon.chains.base import BeaconChain
from eth2.beacon.chains.testnet import TestnetChain
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)
from eth2.beacon.typing import (
    FromBlockParams,
)

from trinity.protocol.bcc.peer import (
    BCCPeer,
)
from trinity.protocol.bcc.servers import (
    BCCReceiveServer,
    OrphanBlockPool,
)
from trinity.protocol.bcc.commands import (
    BeaconBlocks,
)

# from tests.plugins.eth2.beacon.test_validator import (
#     get_chain,
# )

from .helpers import (
    FakeAsyncBeaconChainDB,
    get_genesis_chain_db,
    get_chain_db,
    create_test_block,
    get_directly_linked_peers_in_peer_pools,
)


class FakeChain(TestnetChain):
    chaindb_class = FakeAsyncBeaconChainDB

    timeout = 2
    fake_db = None

    def __init__(self, base_db):
        super().__init__(base_db)
        self.fake_db = {}

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

        self.fake_db[block.signed_root] = block

        (
            new_canonical_blocks,
            old_canonical_blocks,
        ) = self.chaindb.persist_block(block, block.__class__)
        return block, new_canonical_blocks, old_canonical_blocks

    # helper
    def is_block_existing(self, block_root) -> bool:
        return block_root in self.fake_db
        # try:
        #     self.get_block_by_root(block_root)
        #     return True
        # except BlockNotFound:
        #     return False


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

    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)
    bob_receive_server = BCCReceiveServer(chain=bob_chain, peer_pool=bob_peer_pool)

    asyncio.ensure_future(bob_receive_server.run())
    await bob_receive_server.events.started.wait()

    def finalizer():
        event_loop.run_until_complete(bob_receive_server.cancel())

    request.addfinalizer(finalizer)

    return alice, bob_receive_server, msg_buffer


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
    assert pool.get(b1.signed_root) == b1
    assert pool.get(b2.signed_root) == b2
    # test: pop_children
    b2_children = pool.pop_children(b2)
    assert len(b2_children) == 0
    b0_children = pool.pop_children(b0)
    assert len(b0_children) == 2 and (b1 in b0_children) and (b2 in b0_children)


@pytest.mark.asyncio
async def test_bcc_receive_server_try_import_or_handle_orphan(request, event_loop, monkeypatch):
    alice, bob_receive_server, msg_buffer = await get_peer_and_receive_server(request, event_loop)

    def _request_block_by_root(block_root):
        pass

    monkeypatch.setattr(
        bob_receive_server,
        '_request_block_by_root',
        _request_block_by_root,
    )

    bob_chain = bob_receive_server.chain
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
    assert not bob_chain.is_block_existing(block_0.signed_root)
    # test: block with its parent in db should be imported successfully.
    bob_receive_server._try_import_or_handle_orphan(block_0)

    assert bob_chain.is_block_existing(block_0.signed_root)
    # test: block without its parent in db should not be imported, and it should be put in the
    #   `orphan_block_pool`.
    bob_receive_server._try_import_or_handle_orphan(block_2)
    await asyncio.sleep(0)
    assert not bob_chain.is_block_existing(block_2.signed_root)
    assert block_2 in bob_receive_server.orphan_block_pool._pool
    bob_receive_server._try_import_or_handle_orphan(block_3)
    assert not bob_chain.is_block_existing(block_3.signed_root)
    assert block_3 in bob_receive_server.orphan_block_pool._pool
    # test: a successfully imported parent is present, its children should be processed
    #   recursively.
    bob_receive_server._try_import_or_handle_orphan(block_1)
    await asyncio.sleep(0)
    assert bob_chain.is_block_existing(block_1.signed_root)
    assert bob_chain.is_block_existing(block_2.signed_root)
    assert block_2 not in bob_receive_server.orphan_block_pool._pool
    assert bob_chain.is_block_existing(block_3.signed_root)
    assert block_3 not in bob_receive_server.orphan_block_pool._pool
    # TODO: test for requests


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_beacon_blocks(request, event_loop, monkeypatch):
    alice, bob_receive_server, msg_buffer = await get_peer_and_receive_server(request, event_loop)
    bob_chain = bob_receive_server.chain
    head = bob_chain.get_canonical_head()
    block_0 = bob_chain.create_block_from_parent(
        parent_block=head,
        block_params=FromBlockParams(),
    )

    # test: `request_id` not found, it should be rejected
    inexistent_request_id = 5566
    assert inexistent_request_id not in bob_receive_server.map_requested_id_block_root
    alice.sub_proto.send_blocks(blocks=(block_0,), request_id=inexistent_request_id)
    await msg_buffer.msg_queue.get()
    await asyncio.sleep(0)
    assert not bob_chain.is_block_existing(block_0.signed_root)
    # test: >= 1 blocks are sent, the request should be rejected.
    existing_request_id = 1
    bob_receive_server.map_requested_id_block_root[existing_request_id] = block_0.signed_root
    alice.sub_proto.send_blocks(blocks=(block_0, block_0), request_id=existing_request_id)
    await msg_buffer.msg_queue.get()
    assert not bob_chain.is_block_existing(block_0.signed_root)
    # test: `request_id` is found but `block.signed_root` does not correspond to the request
    existing_request_id = 2
    bob_receive_server.map_requested_id_block_root[existing_request_id] = b'\x12' * 32
    alice.sub_proto.send_blocks(blocks=(block_0,), request_id=existing_request_id)
    await msg_buffer.msg_queue.get()
    assert not bob_chain.is_block_existing(block_0.signed_root)
    # test: `request_id` is found and the block is valid. It should be imported.
    existing_request_id = 3
    bob_receive_server.map_requested_id_block_root[existing_request_id] = block_0.signed_root
    alice.sub_proto.send_blocks(blocks=(block_0,), request_id=existing_request_id)
    await msg_buffer.msg_queue.get()
    await asyncio.sleep(0.01)
    assert bob_chain.is_block_existing(block_0.signed_root)
    assert existing_request_id not in bob_receive_server.map_requested_id_block_root


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_new_beacon_block_checks(request, event_loop, monkeypatch):
    alice, bob_receive_server, msg_buffer = await get_peer_and_receive_server(request, event_loop)
    bob_chain = bob_receive_server.chain
    head = bob_chain.get_canonical_head()
    block_0 = bob_chain.create_block_from_parent(
        parent_block=head,
        block_params=FromBlockParams(),
    )
    is_called = False

    def _try_import_or_handle_orphan(block):
        nonlocal is_called
        is_called = True

    monkeypatch.setattr(
        bob_receive_server,
        '_try_import_or_handle_orphan',
        _try_import_or_handle_orphan,
    )

    alice.sub_proto.send_new_block(block=block_0)
    await asyncio.sleep(0.01)
    assert is_called
    is_called = False

    # test: seen blocks should be rejected
    bob_receive_server.orphan_block_pool.add(block_0)
    alice.sub_proto.send_new_block(block=block_0)
    await asyncio.sleep(0.01)
    assert not is_called
