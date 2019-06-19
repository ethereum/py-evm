import asyncio
import functools
import importlib

from typing import (
    Tuple,
)
from async_generator import (
    asynccontextmanager
)

import pytest

import ssz

from eth_utils import (
    ValidationError,
)

from p2p.peer import MsgBuffer
from p2p.tools.factories import PrivateKeyFactory

from eth.exceptions import (
    BlockNotFound,
)

from eth2.beacon.typing import (
    FromBlockParams,
)
from eth2.beacon.chains.base import BaseBeaconChain
from eth2.beacon.chains.testnet import TestnetChain as _TestnetChain
from eth2.beacon.fork_choice.higher_slot import higher_slot_scoring
from eth2.beacon.operations.attestation_pool import AttestationPool as TempPool
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)

from trinity.db.beacon.chain import AsyncBeaconChainDB
from trinity.exceptions import (
    AttestationNotFound,
)
from trinity.protocol.bcc.peer import (
    BCCPeer,
    BCCPeerPoolEventServer,
)
from trinity.protocol.bcc.servers import (
    AttestationPool,
    BCCReceiveServer,
    BCCRequestServer,
    OrphanBlockPool,
)
from eth2.configs import (
    Eth2GenesisConfig,
)

from trinity.tools.bcc_factories import (
    BCCPeerPairFactory,
    BeaconContextFactory,
    BCCPeerPoolFactory,
)

from tests.core.integration_test_helpers import (
    run_peer_pool_event_server,
    run_request_server,
)


bcc_helpers = importlib.import_module('tests.core.p2p-proto.bcc.helpers')


class FakeChain(_TestnetChain):
    chaindb_class = AsyncBeaconChainDB

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
            self.get_block_by_root(block.parent_root)
        except BlockNotFound:
            raise ValidationError
        (
            new_canonical_blocks,
            old_canonical_blocks,
        ) = self.chaindb.persist_block(block, block.__class__, higher_slot_scoring)
        return block, new_canonical_blocks, old_canonical_blocks


async def get_fake_chain() -> FakeChain:
    genesis_config = Eth2GenesisConfig(XIAO_LONG_BAO_CONFIG)
    chain_db = await bcc_helpers.get_genesis_chain_db(genesis_config=genesis_config)
    return FakeChain(
        base_db=chain_db.db,
        attestation_pool=TempPool(),
        genesis_config=genesis_config,
    )


def get_blocks(
        chain: BaseBeaconChain,
        parent_block: SerenityBeaconBlock = None,
        num_blocks: int = 3) -> Tuple[SerenityBeaconBlock, ...]:
    if parent_block is None:
        parent_block = chain.get_canonical_head()
    blocks = []
    for _ in range(num_blocks):
        block = chain.create_block_from_parent(
            parent_block=parent_block,
            block_params=FromBlockParams(),
        )
        blocks.append(block)
        parent_block = block
    return tuple(blocks)


@asynccontextmanager
async def get_peer_and_receive_server(request, event_loop, event_bus) -> Tuple[
        BCCPeer, BCCRequestServer, BCCReceiveServer, asyncio.Queue]:
    alice_chain = await get_fake_chain()
    bob_chain = await get_fake_chain()

    alice_private_key = PrivateKeyFactory()
    bob_private_key = PrivateKeyFactory()

    alice_context = BeaconContextFactory(chain_db=alice_chain.chaindb)
    bob_context = BeaconContextFactory(chain_db=bob_chain.chaindb)
    peer_pair = BCCPeerPairFactory(
        alice_peer_context=alice_context,
        alice_private_key=alice_private_key,
        bob_peer_context=bob_context,
        bob_private_key=bob_private_key,
        event_bus=event_bus,
    )
    async with peer_pair as (alice, bob):
        alice_pool_ctx = BCCPeerPoolFactory.run_for_peer(
            alice,
            privkey=alice_private_key,
            context=alice_context,
            event_bus=event_bus,
        )
        bob_pool_ctx = BCCPeerPoolFactory.run_for_peer(
            bob,
            privkey=bob_private_key,
            context=bob_context,
            event_bus=event_bus,
        )
        async with alice_pool_ctx as alice_peer_pool, bob_pool_ctx as bob_peer_pool:
            msg_queue = asyncio.Queue()
            orig_handle_msg = BCCReceiveServer._handle_msg

            # Inject a queue to each `BCCReceiveServer`, which puts the message
            # passed to `_handle_msg` to the queue, right after every `_handle_msg`
            # finishes.  This is crucial to make the test be able to wait until
            # `_handle_msg` finishes.
            async def _handle_msg(self, base_peer, cmd, msg):
                task = asyncio.ensure_future(orig_handle_msg(self, base_peer, cmd, msg))

                def enqueue_msg(future, msg):
                    msg_queue.put_nowait(msg)
                task.add_done_callback(functools.partial(enqueue_msg, msg=msg))
                await task
            BCCReceiveServer._handle_msg = _handle_msg

            async with run_peer_pool_event_server(
                event_bus, alice_peer_pool, BCCPeerPoolEventServer
            ), run_request_server(
                event_bus, alice_chain.chaindb, server_type=BCCRequestServer
            ) as alice_req_server:

                bob_recv_server = BCCReceiveServer(chain=bob_chain, peer_pool=bob_peer_pool)

                asyncio.ensure_future(bob_recv_server.run())
                await bob_recv_server.events.started.wait()

                def finalizer():
                    event_loop.run_until_complete(bob_recv_server.cancel())

                request.addfinalizer(finalizer)

                yield alice, alice_req_server, bob_recv_server, msg_queue


def test_orphan_block_pool():
    pool = OrphanBlockPool()
    b0 = bcc_helpers.create_test_block()
    b1 = bcc_helpers.create_test_block(parent=b0)
    b2 = bcc_helpers.create_test_block(parent=b0, state_root=b"\x11" * 32)
    # test: add
    pool.add(b1)
    assert b1 in pool._pool
    assert len(pool._pool) == 1
    # test: add: no side effect for adding twice
    pool.add(b1)
    assert len(pool._pool) == 1
    # test: `__contains__`
    assert b1 in pool
    assert b1.signing_root in pool
    assert b2 not in pool
    assert b2.signing_root not in pool
    # test: add: two blocks
    pool.add(b2)
    assert len(pool._pool) == 2
    # test: get
    assert pool.get(b1.signing_root) == b1
    assert pool.get(b2.signing_root) == b2
    # test: pop_children
    b2_children = pool.pop_children(b2.signing_root)
    assert len(b2_children) == 0
    assert len(pool._pool) == 2
    b0_children = pool.pop_children(b0.signing_root)
    assert len(b0_children) == 2 and (b1 in b0_children) and (b2 in b0_children)
    assert len(pool._pool) == 0


@pytest.mark.asyncio
async def test_bcc_receive_server_try_import_orphan_blocks(request,
                                                           event_loop,
                                                           event_bus,
                                                           monkeypatch):

    async with get_peer_and_receive_server(
        request, event_loop, event_bus
    ) as (_, _, bob_recv_server, _):

        blocks = get_blocks(bob_recv_server.chain, num_blocks=4)
        assert not bob_recv_server._is_block_root_in_db(blocks[0].signing_root)
        bob_recv_server.chain.import_block(blocks[0])

        assert bob_recv_server._is_block_root_in_db(blocks[0].signing_root)
        # test: block without its parent in db should not be imported, and it should be put in the
        #   `orphan_block_pool`.
        bob_recv_server.orphan_block_pool.add(blocks[2])
        # test: No effect when calling `_try_import_orphan_blocks`
        # if the `parent_root` is not in db.
        assert blocks[2].parent_root == blocks[1].signing_root
        bob_recv_server._try_import_orphan_blocks(blocks[2].parent_root)
        assert not bob_recv_server._is_block_root_in_db(blocks[2].parent_root)
        assert not bob_recv_server._is_block_root_in_db(blocks[2].signing_root)
        assert bob_recv_server._is_block_root_in_orphan_block_pool(blocks[2].signing_root)

        bob_recv_server.orphan_block_pool.add(blocks[3])
        # test: No effect when calling `_try_import_orphan_blocks` if `parent_root` is in the pool
        #   but not in db.
        assert blocks[3].parent_root == blocks[2].signing_root
        bob_recv_server._try_import_orphan_blocks(blocks[2].signing_root)
        assert not bob_recv_server._is_block_root_in_db(blocks[2].signing_root)
        assert not bob_recv_server._is_block_root_in_db(blocks[3].signing_root)
        assert bob_recv_server._is_block_root_in_orphan_block_pool(blocks[3].signing_root)
        # test: a successfully imported parent is present, its children should be processed
        #   recursively.
        bob_recv_server.chain.import_block(blocks[1])
        bob_recv_server._try_import_orphan_blocks(blocks[1].signing_root)
        assert bob_recv_server._is_block_root_in_db(blocks[1].signing_root)
        assert bob_recv_server._is_block_root_in_db(blocks[2].signing_root)
        assert bob_recv_server._is_block_root_in_db(blocks[3].signing_root)
        assert not bob_recv_server._is_block_root_in_orphan_block_pool(blocks[2].signing_root)
        assert not bob_recv_server._is_block_root_in_orphan_block_pool(blocks[3].signing_root)


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_beacon_blocks_checks(request,
                                                              event_loop,
                                                              event_bus,
                                                              monkeypatch):

    async with get_peer_and_receive_server(
        request,
        event_loop,
        event_bus,
    ) as (alice, _, bob_recv_server, bob_msg_queue):

        blocks = get_blocks(bob_recv_server.chain, num_blocks=1)

        event = asyncio.Event()

        def _process_received_block(block):
            event.set()

        monkeypatch.setattr(
            bob_recv_server,
            '_process_received_block',
            _process_received_block,
        )

        # test: `request_id` not found, it should be rejected
        inexistent_request_id = 5566
        assert inexistent_request_id not in bob_recv_server.map_request_id_block_root
        alice.sub_proto.send_blocks(blocks=(blocks[0],), request_id=inexistent_request_id)
        await bob_msg_queue.get()
        assert not event.is_set()

        # test: >= 1 blocks are sent, the request should be rejected.
        event.clear()
        existing_request_id = 1
        bob_recv_server.map_request_id_block_root[existing_request_id] = blocks[0].signing_root
        alice.sub_proto.send_blocks(blocks=(blocks[0], blocks[0]), request_id=existing_request_id)
        await bob_msg_queue.get()
        assert not event.is_set()

        # test: `request_id` is found but `block.signing_root` does not correspond to the request
        event.clear()
        existing_request_id = 2
        bob_recv_server.map_request_id_block_root[existing_request_id] = b'\x12' * 32
        alice.sub_proto.send_blocks(blocks=(blocks[0],), request_id=existing_request_id)
        await bob_msg_queue.get()
        assert not event.is_set()

        # test: `request_id` is found and the block is valid. It should be imported.
        event.clear()
        existing_request_id = 3
        bob_recv_server.map_request_id_block_root[existing_request_id] = blocks[0].signing_root
        alice.sub_proto.send_blocks(blocks=(blocks[0],), request_id=existing_request_id)
        await bob_msg_queue.get()
        assert event.is_set()
        # ensure `request_id` is cleared after successful response
        assert existing_request_id not in bob_recv_server.map_request_id_block_root


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_new_beacon_block_checks(request,
                                                                 event_loop,
                                                                 event_bus,
                                                                 monkeypatch):

    async with get_peer_and_receive_server(
        request,
        event_loop,
        event_bus,
    ) as (alice, _, bob_recv_server, bob_msg_queue):
        blocks = get_blocks(bob_recv_server.chain, num_blocks=1)

        event = asyncio.Event()

        def _process_received_block(block):
            event.set()

        monkeypatch.setattr(
            bob_recv_server,
            '_process_received_block',
            _process_received_block,
        )

        alice.sub_proto.send_new_block(block=blocks[0])
        await bob_msg_queue.get()
        assert event.is_set()

        # test: seen blocks should be rejected
        event.clear()
        bob_recv_server.orphan_block_pool.add(blocks[0])
        alice.sub_proto.send_new_block(block=blocks[0])
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
async def test_bcc_receive_request_block_by_root(request, event_loop, event_bus):
    async with get_peer_and_receive_server(
        request,
        event_loop,
        event_bus,
    ) as (alice, alice_req_server, bob_recv_server, bob_msg_queue):
        alice_msg_buffer = MsgBuffer()
        alice.add_subscriber(alice_msg_buffer)
        blocks = get_blocks(bob_recv_server.chain, num_blocks=1)

        # test: request from bob is issued and received by alice
        bob_recv_server._request_block_from_peers(blocks[0].signing_root)
        req = await alice_msg_buffer.msg_queue.get()
        assert req.payload['block_slot_or_root'] == blocks[0].signing_root

        # test: alice responds to the bob's request
        await alice_req_server.db.coro_persist_block(
            blocks[0],
            SerenityBeaconBlock,
            higher_slot_scoring,
        )
        bob_recv_server._request_block_from_peers(blocks[0].signing_root)
        msg_block = await bob_msg_queue.get()
        assert blocks[0] == parse_resp_block_msg(msg_block)


@pytest.mark.asyncio
async def test_bcc_receive_server_process_received_block(request,
                                                         event_loop,
                                                         event_bus,
                                                         monkeypatch):

    async with get_peer_and_receive_server(
        request,
        event_loop,
        event_bus,
    ) as (_, _, bob_recv_server, _):

        block_not_orphan, block_orphan = get_blocks(bob_recv_server.chain, num_blocks=2)

        # test: if the block is an orphan, puts it in the orphan pool, calls
        #   `_request_block_from_peers`, and returns `False`.
        event = asyncio.Event()

        def _request_block_from_peers(block_root):
            event.set()
        with monkeypatch.context() as m:
            m.setattr(bob_recv_server, '_request_block_from_peers', _request_block_from_peers)
            assert not bob_recv_server._process_received_block(block_orphan)
            assert bob_recv_server.orphan_block_pool.get(block_orphan.signing_root) == block_orphan
            assert event.is_set()

        # test: should returns `False` if `ValidationError` occurs.
        def import_block_raises_validation_error(block, performa_validation=True):
            raise ValidationError
        with monkeypatch.context() as m:
            m.setattr(bob_recv_server.chain, 'import_block', import_block_raises_validation_error)
            assert not bob_recv_server._process_received_block(block_not_orphan)

        # test: other exceptions occurred when importing the block.
        class OtherException(Exception):
            pass

        def import_block_raises_other_exception_error(block, performa_validation=True):
            raise OtherException

        with monkeypatch.context() as m:
            m.setattr(
                bob_recv_server.chain, 'import_block', import_block_raises_other_exception_error)
            with pytest.raises(OtherException):
                bob_recv_server._process_received_block(block_not_orphan)

        # test: successfully imported the block, calls `self._try_import_orphan_blocks`,
        #   and returns `True`.
        event.clear()

        def _try_import_orphan_blocks(parent_root):
            event.set()
        with monkeypatch.context() as m:
            m.setattr(bob_recv_server, '_try_import_orphan_blocks', _try_import_orphan_blocks)
            assert bob_recv_server._process_received_block(block_not_orphan)
            assert event.is_set()


@pytest.mark.asyncio
async def test_bcc_receive_server_broadcast_block(request, event_loop, event_bus, monkeypatch):
    async with get_peer_and_receive_server(
        request,
        event_loop,
        event_bus,
    ) as (alice, _, bob_recv_server, _):

        block_non_orphan, block_orphan = get_blocks(bob_recv_server.chain, num_blocks=2)
        alice_msg_buffer = MsgBuffer()
        alice.add_subscriber(alice_msg_buffer)

        # test: with `from_peer=alice`, bob broadcasts to all peers except alice. Therefore, alice
        #   should fail to receive the block.
        bob_peers = bob_recv_server._peer_pool.connected_nodes.values()
        assert len(bob_peers) == 1
        alice_in_bobs_peer_pool = tuple(bob_peers)[0]
        # NOTE: couldn't use `alice` directly, `from_peer` should be a `BCCPeer` in its PeerPool
        bob_recv_server._broadcast_block(block_orphan, from_peer=alice_in_bobs_peer_pool)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(alice_msg_buffer.msg_queue.get(), 0.1)

        # test: with `from_peer=None` it broadcasts the block to all bob's peers.
        # Try the orphan block first.
        bob_recv_server._broadcast_block(block_orphan, from_peer=None)
        msg_block_orphan = await alice_msg_buffer.msg_queue.get()
        block_orphan_received = parse_new_block_msg(msg_block_orphan.payload)
        assert block_orphan_received.signing_root == block_orphan.signing_root

        # test: Try the non-orphan block.
        bob_recv_server._broadcast_block(block_non_orphan, from_peer=None)
        msg_block_orphan = await alice_msg_buffer.msg_queue.get()
        block_non_orphan_received = parse_new_block_msg(msg_block_orphan.payload)
        assert block_non_orphan_received.signing_root == block_non_orphan.signing_root


@pytest.mark.asyncio
async def test_bcc_receive_server_with_request_server(request, event_loop, event_bus):
    async with get_peer_and_receive_server(
        request,
        event_loop,
        event_bus,
    ) as (alice, alice_req_server, bob_recv_server, bob_msg_queue):

        alice_msg_buffer = MsgBuffer()
        alice.add_subscriber(alice_msg_buffer)
        blocks = get_blocks(bob_recv_server.chain, num_blocks=3)
        await alice_req_server.db.coro_persist_block(
            blocks[0],
            SerenityBeaconBlock,
            higher_slot_scoring,
        )
        await alice_req_server.db.coro_persist_block(
            blocks[1],
            SerenityBeaconBlock,
            higher_slot_scoring,
        )
        await alice_req_server.db.coro_persist_block(
            blocks[2],
            SerenityBeaconBlock,
            higher_slot_scoring,
        )

        # test: alice send `blocks[2]` to bob, and bob should be able to
        # get `blocks[1]` and `blocks[0]` later through the requests.
        assert not bob_recv_server._is_block_seen(blocks[0])
        assert not bob_recv_server._is_block_seen(blocks[1])
        assert not bob_recv_server._is_block_seen(blocks[2])
        alice.sub_proto.send_new_block(block=blocks[2])
        # bob receives new block `blocks[2]`
        assert blocks[2] == parse_new_block_msg(await bob_msg_queue.get())
        # bob requests for `blocks[1]`, and alice receives the request
        req_1 = await alice_msg_buffer.msg_queue.get()
        assert req_1.payload['block_slot_or_root'] == blocks[1].signing_root
        # bob receives the response block `blocks[1]`
        assert blocks[1] == parse_resp_block_msg(await bob_msg_queue.get())
        # bob requests for `blocks[0]`, and alice receives the request
        req_0 = await alice_msg_buffer.msg_queue.get()
        assert req_0.payload['block_slot_or_root'] == blocks[0].signing_root
        # bob receives the response block `blocks[0]`
        assert blocks[0] == parse_resp_block_msg(await bob_msg_queue.get())
        assert bob_recv_server._is_block_root_in_db(blocks[0].signing_root)
        assert bob_recv_server._is_block_root_in_db(blocks[1].signing_root)
        assert bob_recv_server._is_block_root_in_db(blocks[2].signing_root)


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_attestations_checks(request,
                                                             event_loop,
                                                             event_bus,
                                                             monkeypatch):
    async with get_peer_and_receive_server(
        request,
        event_loop,
        event_bus,
    ) as (alice, _, bob_recv_server, bob_msg_queue):

        attestation = Attestation()

        def _validate_attestations(attestations):
            return tuple(attestations)

        monkeypatch.setattr(
            bob_recv_server,
            '_validate_attestations',
            _validate_attestations,
        )

        alice.sub_proto.send_attestation_records([attestation])
        msg = await bob_msg_queue.get()
        assert len(msg['encoded_attestations']) == 1
        decoded_attestation = ssz.decode(msg['encoded_attestations'][0], Attestation)
        assert decoded_attestation == attestation


def test_attestation_pool():
    pool = AttestationPool()
    a1 = Attestation()
    a2 = Attestation(
        data=a1.data.copy(
            beacon_block_root=b'\x55' * 32,
        ),
    )
    a3 = Attestation(
        data=a1.data.copy(
            beacon_block_root=b'\x66' * 32,
        ),
    )

    # test: add
    pool.add(a1)
    assert a1 in pool._pool
    assert len(pool._pool) == 1
    # test: add: no side effect for adding twice
    pool.add(a1)
    assert len(pool._pool) == 1
    # test: `__contains__`
    assert a1.hash_tree_root in pool
    assert a1 in pool
    assert a2.hash_tree_root not in pool
    assert a2 not in pool
    # test: batch_add: two attestations
    pool.batch_add([a1, a2])
    assert len(pool._pool) == 2
    # test: get
    with pytest.raises(AttestationNotFound):
        pool.get(a3.hash_tree_root)
    assert pool.get(a1.hash_tree_root) == a1
    assert pool.get(a2.hash_tree_root) == a2
    # test: get_all
    assert set([a1, a2]) == set(pool.get_all())
    # test: remove
    pool.remove(a3)
    assert len(pool._pool) == 2
    pool.batch_remove([a2, a1])
    assert len(pool._pool) == 0


@pytest.mark.asyncio
async def test_bcc_receive_server_get_ready_attestations(
        request,
        event_loop,
        event_bus,
        mocker):
    async with get_peer_and_receive_server(
        request,
        event_loop,
        event_bus,
    ) as (alice, _, bob_recv_server, _):
        class MockState:
            slot = XIAO_LONG_BAO_CONFIG.GENESIS_SLOT
        state = MockState()

        def mock_get_head_state(self):
            return state

        def mock_get_attestation_data_slot(state, data, config):
            return data.slot
        mocker.patch("eth2.beacon.chains.base.BeaconChain.get_head_state", mock_get_head_state)
        mocker.patch(
            "trinity.protocol.bcc.servers.get_attestation_data_slot",
            mock_get_attestation_data_slot,
        )
        attesting_slot = XIAO_LONG_BAO_CONFIG.GENESIS_SLOT
        a1 = Attestation(data=AttestationData())
        a1.data.slot = attesting_slot
        a2 = Attestation(signature=b'\x56' * 96, data=AttestationData())
        a2.data.slot = attesting_slot
        a3 = Attestation(signature=b'\x78' * 96, data=AttestationData())
        a3.data.slot = attesting_slot + 1
        bob_recv_server.attestation_pool.batch_add([a1, a2, a3])

        # Workaround: add a fake head state slot
        # so `get_state_machine` wont's trigger `HeadStateSlotNotFound` exception
        bob_recv_server.chain.chaindb._add_head_state_slot_lookup(XIAO_LONG_BAO_CONFIG.GENESIS_SLOT)

        state.slot = attesting_slot + XIAO_LONG_BAO_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY - 1
        ready_attestations = bob_recv_server.get_ready_attestations()
        assert len(ready_attestations) == 0

        state.slot = attesting_slot + XIAO_LONG_BAO_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY
        ready_attestations = bob_recv_server.get_ready_attestations()
        assert set([a1, a2]) == set(ready_attestations)

        state.slot = attesting_slot + XIAO_LONG_BAO_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY + 1
        ready_attestations = bob_recv_server.get_ready_attestations()
        assert set([a1, a2, a3]) == set(ready_attestations)

        state.slot = attesting_slot + XIAO_LONG_BAO_CONFIG.SLOTS_PER_EPOCH + 1
        ready_attestations = bob_recv_server.get_ready_attestations()
        assert set([a3]) == set(ready_attestations)
