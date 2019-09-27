import asyncio
from typing import Tuple

from eth.exceptions import BlockNotFound
from eth_utils import ValidationError
from libp2p.pubsub.pb import rpc_pb2
import pytest
import ssz

from eth2.beacon.chains.base import BaseBeaconChain
from eth2.beacon.chains.testnet import TestnetChain as _TestnetChain
from eth2.beacon.fork_choice.higher_slot import higher_slot_scoring
from eth2.beacon.operations.attestation_pool import AttestationPool as TempPool
from eth2.beacon.state_machines.forks.serenity.blocks import SerenityBeaconBlock
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import XIAO_LONG_BAO_CONFIG
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.blocks import BaseBeaconBlock, BeaconBlock
from eth2.beacon.typing import FromBlockParams
from eth2.configs import Eth2GenesisConfig
from trinity.db.beacon.chain import AsyncBeaconChainDB
from trinity.protocol.bcc_libp2p.configs import (
    PUBSUB_TOPIC_BEACON_ATTESTATION,
    PUBSUB_TOPIC_BEACON_BLOCK,
)
from trinity.protocol.bcc_libp2p.servers import AttestationPool, OrphanBlockPool
from trinity.tools.bcc_factories import (
    AsyncBeaconChainDBFactory,
    BeaconBlockFactory,
    ReceiveServerFactory,
)


class FakeChain(_TestnetChain):
    chaindb_class = AsyncBeaconChainDB

    def import_block(
        self, block: BaseBeaconBlock, perform_validation: bool = True
    ) -> Tuple[
        BaseBeaconBlock, Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]
    ]:
        """
        Remove the logics about `state`, because we only need to check a block's parent in
        `ReceiveServer`.
        """
        try:
            self.get_block_by_root(block.parent_root)
        except BlockNotFound:
            raise ValidationError
        (new_canonical_blocks, old_canonical_blocks) = self.chaindb.persist_block(
            block, block.__class__, higher_slot_scoring
        )
        return block, new_canonical_blocks, old_canonical_blocks


async def get_fake_chain() -> FakeChain:
    genesis_config = Eth2GenesisConfig(XIAO_LONG_BAO_CONFIG)
    chain_db = AsyncBeaconChainDBFactory(genesis_config=genesis_config)
    return FakeChain(
        base_db=chain_db.db, attestation_pool=TempPool(), genesis_config=genesis_config
    )


def get_blocks(
    chain: BaseBeaconChain,
    parent_block: SerenityBeaconBlock = None,
    num_blocks: int = 3,
) -> Tuple[SerenityBeaconBlock, ...]:
    if parent_block is None:
        parent_block = chain.get_canonical_head()
    blocks = []
    for _ in range(num_blocks):
        block = chain.create_block_from_parent(
            parent_block=parent_block, block_params=FromBlockParams()
        )
        blocks.append(block)
        parent_block = block
    return tuple(blocks)


@pytest.fixture
async def receive_server():
    topic_msg_queues = {
        PUBSUB_TOPIC_BEACON_BLOCK: asyncio.Queue(),
        PUBSUB_TOPIC_BEACON_ATTESTATION: asyncio.Queue(),
    }
    chain = await get_fake_chain()
    server = ReceiveServerFactory(chain=chain, topic_msg_queues=topic_msg_queues)
    asyncio.ensure_future(server.run())
    await server.events.started.wait()
    try:
        yield server
    finally:
        await server.cancel()


@pytest.fixture
async def receive_server_with_mock_process_orphan_blocks_period(
    mock_process_orphan_blocks_period
):
    topic_msg_queues = {
        PUBSUB_TOPIC_BEACON_BLOCK: asyncio.Queue(),
        PUBSUB_TOPIC_BEACON_ATTESTATION: asyncio.Queue(),
    }
    chain = await get_fake_chain()
    server = ReceiveServerFactory(chain=chain, topic_msg_queues=topic_msg_queues)
    asyncio.ensure_future(server.run())
    await server.events.started.wait()
    try:
        yield server
    finally:
        await server.cancel()


def test_attestation_pool():
    pool = AttestationPool()
    a1 = Attestation()
    a2 = Attestation(data=a1.data.copy(beacon_block_root=b"\x55" * 32))
    a3 = Attestation(data=a1.data.copy(beacon_block_root=b"\x66" * 32))

    # test: add
    pool.add(a1)
    assert a1.hash_tree_root in pool._pool_storage
    assert len(pool) == 1
    # test: add: no side effect for adding twice
    pool.add(a1)
    assert len(pool) == 1
    # test: `__contains__`
    assert a1.hash_tree_root in pool
    assert a1 in pool
    assert a2.hash_tree_root not in pool
    assert a2 not in pool
    # test: batch_add: two attestations
    pool.batch_add([a1, a2])
    assert len(pool) == 2
    # test: get
    with pytest.raises(KeyError):
        pool.get(a3.hash_tree_root)
    assert pool.get(a1.hash_tree_root) == a1
    assert pool.get(a2.hash_tree_root) == a2
    # test: get_all
    assert set([a1, a2]) == set(pool.get_all())
    # test: remove
    pool.remove(a3)
    assert len(pool) == 2
    pool.batch_remove([a2, a1])
    assert len(pool) == 0


def test_orphan_block_pool():
    pool = OrphanBlockPool()
    b0 = BeaconBlockFactory()
    b1 = BeaconBlockFactory(parent=b0)
    b2 = BeaconBlockFactory(parent=b0, state_root=b"\x11" * 32)
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
async def test_bcc_receive_server_try_import_orphan_blocks(receive_server):
    blocks = get_blocks(receive_server.chain, num_blocks=4)

    assert not receive_server._is_block_root_in_db(blocks[0].signing_root)
    receive_server.chain.import_block(blocks[0])
    assert receive_server._is_block_root_in_db(blocks[0].signing_root)

    # test: block without its parent in db should not be imported, and it should be put in the
    # `orphan_block_pool`.
    receive_server.orphan_block_pool.add(blocks[2])
    # test: No effect when calling `_try_import_orphan_blocks`
    # if the `parent_root` is not in db.
    assert blocks[2].parent_root == blocks[1].signing_root
    receive_server._try_import_orphan_blocks(blocks[2].parent_root)
    assert not receive_server._is_block_root_in_db(blocks[2].parent_root)
    assert not receive_server._is_block_root_in_db(blocks[2].signing_root)
    assert receive_server._is_block_root_in_orphan_block_pool(blocks[2].signing_root)

    receive_server.orphan_block_pool.add(blocks[3])
    # test: No effect when calling `_try_import_orphan_blocks` if `parent_root` is in the pool
    # but not in db.
    assert blocks[3].parent_root == blocks[2].signing_root
    receive_server._try_import_orphan_blocks(blocks[2].signing_root)
    assert not receive_server._is_block_root_in_db(blocks[2].signing_root)
    assert not receive_server._is_block_root_in_db(blocks[3].signing_root)
    assert receive_server._is_block_root_in_orphan_block_pool(blocks[3].signing_root)

    # test: a successfully imported parent is present, its children should be processed
    # recursively.
    receive_server.chain.import_block(blocks[1])
    receive_server._try_import_orphan_blocks(blocks[1].signing_root)
    assert receive_server._is_block_root_in_db(blocks[1].signing_root)
    assert receive_server._is_block_root_in_db(blocks[2].signing_root)
    assert receive_server._is_block_root_in_db(blocks[3].signing_root)
    assert not receive_server._is_block_root_in_orphan_block_pool(
        blocks[2].signing_root
    )
    assert not receive_server._is_block_root_in_orphan_block_pool(
        blocks[3].signing_root
    )


@pytest.mark.asyncio
async def test_bcc_receive_server_process_received_block(receive_server, monkeypatch):
    block_not_orphan, block_orphan = get_blocks(receive_server.chain, num_blocks=2)

    # test: if the block is an orphan, puts it in the orphan pool
    receive_server._process_received_block(block_orphan)
    assert (
        receive_server.orphan_block_pool.get(block_orphan.signing_root) == block_orphan
    )

    # test: should returns `False` if `ValidationError` occurs.
    def import_block_raises_validation_error(block, performa_validation=True):
        raise ValidationError

    with monkeypatch.context() as m:
        m.setattr(
            receive_server.chain, "import_block", import_block_raises_validation_error
        )
        receive_server._process_received_block(block_not_orphan)
        assert not receive_server._is_block_root_in_db(block_not_orphan.signing_root)

    # test: successfully imported the block, calls `self._try_import_orphan_blocks`
    event = asyncio.Event()

    def _try_import_orphan_blocks(parent_root):
        event.set()

    with monkeypatch.context() as m:
        m.setattr(
            receive_server, "_try_import_orphan_blocks", _try_import_orphan_blocks
        )
        receive_server._process_received_block(block_not_orphan)
        assert event.is_set()


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_beacon_blocks(receive_server):
    block = get_blocks(receive_server.chain, num_blocks=1)[0]
    encoded_block = ssz.encode(block, BeaconBlock)
    msg = rpc_pb2.Message(
        from_id=b"my_id",
        seqno=b"\x00" * 8,
        data=encoded_block,
        topicIDs=[PUBSUB_TOPIC_BEACON_BLOCK],
    )

    assert receive_server.chain.get_canonical_head() != block

    beacon_block_queue = receive_server.topic_msg_queues[PUBSUB_TOPIC_BEACON_BLOCK]
    await beacon_block_queue.put(msg)
    # Wait for receive server to process the new block
    await asyncio.sleep(0.5)
    assert receive_server.chain.get_canonical_head() == block


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_beacon_attestations(receive_server):
    attestation = Attestation()
    encoded_attestation = ssz.encode(attestation)
    msg = rpc_pb2.Message(
        from_id=b"my_id",
        seqno=b"\x00" * 8,
        data=encoded_attestation,
        topicIDs=[PUBSUB_TOPIC_BEACON_ATTESTATION],
    )

    assert attestation not in receive_server.attestation_pool

    beacon_attestation_queue = receive_server.topic_msg_queues[
        PUBSUB_TOPIC_BEACON_ATTESTATION
    ]
    await beacon_attestation_queue.put(msg)
    # Wait for receive server to process the new attestation
    await asyncio.sleep(0.5)
    # Check that attestation is put to attestation pool
    assert attestation in receive_server.attestation_pool

    # Put the attestation in the next block
    block = get_blocks(receive_server.chain, num_blocks=1)[0]
    block = block.copy(body=block.body.copy(attestations=[attestation]))
    encoded_block = ssz.encode(block, BeaconBlock)
    msg = rpc_pb2.Message(
        from_id=b"my_id",
        seqno=b"\x00" * 8,
        data=encoded_block,
        topicIDs=[PUBSUB_TOPIC_BEACON_BLOCK],
    )

    beacon_block_queue = receive_server.topic_msg_queues[PUBSUB_TOPIC_BEACON_BLOCK]
    await beacon_block_queue.put(msg)
    # Wait for receive server to process the new block
    await asyncio.sleep(0.5)
    # Check that attestation is removed from attestation pool
    assert attestation not in receive_server.attestation_pool


@pytest.mark.asyncio
async def test_bcc_receive_server_handle_orphan_block_loop(
    receive_server_with_mock_process_orphan_blocks_period, monkeypatch
):
    receive_server = receive_server_with_mock_process_orphan_blocks_period
    # block dependency graph
    # block 1  -- block 2 -- block 3 -- block 4 -- block 5
    #                 |   \
    #                 |    block 3'
    #              block 3''
    #
    # block 5, 3' and 3'' are orphan blocks
    #
    # First iteration will request block 4 and block 2 and import block 2, block 3' and block 3'',
    # second iteration will request block 3 and import block 3, block 4 and block 5.
    blocks = get_blocks(receive_server.chain, num_blocks=5)
    fork_blocks = (
        blocks[2].copy(state_root=b"\x01" * 32),
        blocks[2].copy(state_root=b"\x12" * 32),
    )
    mock_peer_1_db = {block.signing_root: block for block in blocks[3:]}
    mock_peer_2_db = {block.signing_root: block for block in blocks[:3]}

    receive_server.chain.import_block(blocks[0])

    fake_peers = [b"peer_1", b"peer_2"]
    peer_1_called_event = asyncio.Event()
    peer_2_called_event = asyncio.Event()

    async def request_recent_beacon_blocks(peer_id, block_roots):
        requested_blocks = []
        db = {}
        if peer_id == fake_peers[0]:
            db = mock_peer_1_db
            peer_1_called_event.set()
        elif peer_id == fake_peers[1]:
            db = mock_peer_2_db
            peer_2_called_event.set()

        for block_root in block_roots:
            if block_root in db:
                requested_blocks.append(db[block_root])
        return requested_blocks

    with monkeypatch.context() as m:
        m.setattr(receive_server.p2p_node, "handshaked_peers", set(fake_peers))
        m.setattr(
            receive_server.p2p_node,
            "request_recent_beacon_blocks",
            request_recent_beacon_blocks,
        )

        for orphan_block in (blocks[4],) + fork_blocks:
            receive_server.orphan_block_pool.add(orphan_block)
        # Wait for receive server to process the orphan blocks
        await asyncio.sleep(0.5)
        # Check that both peers were requested for blocks
        assert peer_1_called_event.is_set()
        assert peer_2_called_event.is_set()
        # Check that all blocks are processed and no more orphan blocks
        for block in blocks + fork_blocks:
            assert receive_server._is_block_root_in_db(block.signing_root)
        assert len(receive_server.orphan_block_pool) == 0


@pytest.mark.asyncio
async def test_bcc_receive_server_get_ready_attestations(receive_server, monkeypatch):
    class MockState:
        slot = XIAO_LONG_BAO_CONFIG.GENESIS_SLOT

    state = MockState()

    def mock_get_head_state():
        return state

    def mock_get_attestation_data_slot(state, data, config):
        return data.slot

    monkeypatch.setattr(receive_server.chain, "get_head_state", mock_get_head_state)
    from trinity.protocol.bcc_libp2p import servers

    monkeypatch.setattr(
        servers, "get_attestation_data_slot", mock_get_attestation_data_slot
    )
    attesting_slot = XIAO_LONG_BAO_CONFIG.GENESIS_SLOT
    a1 = Attestation(data=AttestationData())
    a1.data.slot = attesting_slot
    a2 = Attestation(signature=b"\x56" * 96, data=AttestationData())
    a2.data.slot = attesting_slot
    a3 = Attestation(signature=b"\x78" * 96, data=AttestationData())
    a3.data.slot = attesting_slot + 1
    receive_server.attestation_pool.batch_add([a1, a2, a3])

    # Workaround: add a fake head state slot
    # so `get_state_machine` won't trigger `HeadStateSlotNotFound` exception
    receive_server.chain.chaindb._add_head_state_slot_lookup(
        XIAO_LONG_BAO_CONFIG.GENESIS_SLOT
    )

    state.slot = (
        attesting_slot + XIAO_LONG_BAO_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY - 1
    )
    ready_attestations = receive_server.get_ready_attestations()
    assert len(ready_attestations) == 0

    state.slot = attesting_slot + XIAO_LONG_BAO_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY
    ready_attestations = receive_server.get_ready_attestations()
    assert set([a1, a2]) == set(ready_attestations)

    state.slot = (
        attesting_slot + XIAO_LONG_BAO_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY + 1
    )
    ready_attestations = receive_server.get_ready_attestations()
    assert set([a1, a2, a3]) == set(ready_attestations)

    state.slot = attesting_slot + XIAO_LONG_BAO_CONFIG.SLOTS_PER_EPOCH + 1
    ready_attestations = receive_server.get_ready_attestations()
    assert set([a3]) == set(ready_attestations)
