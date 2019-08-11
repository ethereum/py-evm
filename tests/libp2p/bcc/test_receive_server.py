import asyncio
import importlib

from typing import (
    Tuple,
)

import pytest

import ssz

from eth_utils import (
    ValidationError,
)

from eth2.configs import (
    Eth2GenesisConfig,
)
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
    BeaconBlock,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)

from libp2p.pubsub.pb import rpc_pb2

from trinity.exceptions import (
    AttestationNotFound,
)
from trinity.protocol.bcc_libp2p.servers import (
    AttestationPool,
    BCCReceiveServer,
)
from trinity.protocol.bcc_libp2p.configs import (
    PUBSUB_TOPIC_BEACON_BLOCK,
    PUBSUB_TOPIC_BEACON_ATTESTATION,
    SSZ_MAX_LIST_SIZE,
)


bcc_helpers = importlib.import_module('tests.core.p2p-proto.bcc.helpers')


class FakeChain(_TestnetChain):
    chaindb_class = bcc_helpers.FakeAsyncBeaconChainDB

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


@pytest.fixture
async def receive_server():
    topic_msg_queues = {
        PUBSUB_TOPIC_BEACON_BLOCK: asyncio.Queue(),
        PUBSUB_TOPIC_BEACON_ATTESTATION: asyncio.Queue(),
    }
    chain = await get_fake_chain()
    server = BCCReceiveServer(
        chain,
        topic_msg_queues,
    )
    asyncio.ensure_future(server.run())
    await server.events.started.wait()
    try:
        yield server
    finally:
        await server.cancel()


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
async def test_bcc_receive_server_handle_beacon_blocks(receive_server):
    block = get_blocks(receive_server.chain, num_blocks=1)[0]
    encoded_block = ssz.encode(block, BeaconBlock)
    msg = rpc_pb2.Message(
        from_id=b"my_id",
        seqno=b"\x00" * 8,
        data=encoded_block,
        topicIDs=[PUBSUB_TOPIC_BEACON_BLOCK]
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
    encoded_attestations = ssz.encode([attestation], sedes=ssz.List(Attestation, SSZ_MAX_LIST_SIZE))
    msg = rpc_pb2.Message(
        from_id=b"my_id",
        seqno=b"\x00" * 8,
        data=encoded_attestations,
        topicIDs=[PUBSUB_TOPIC_BEACON_ATTESTATION]
    )

    assert attestation not in receive_server.attestation_pool

    beacon_attestation_queue = receive_server.topic_msg_queues[PUBSUB_TOPIC_BEACON_ATTESTATION]
    await beacon_attestation_queue.put(msg)
    # Wait for receive server to process the new attestation
    await asyncio.sleep(0.5)
    # Check that attestation is put to attestation pool
    assert attestation in receive_server.attestation_pool

    # Put the attestation in the next block
    block = get_blocks(receive_server.chain, num_blocks=1)[0]
    block = block.copy(
        body=block.body.copy(
            attestations=[attestation],
        )
    )
    encoded_block = ssz.encode(block, BeaconBlock)
    msg = rpc_pb2.Message(
        from_id=b"my_id",
        seqno=b"\x00" * 8,
        data=encoded_block,
        topicIDs=[PUBSUB_TOPIC_BEACON_BLOCK]
    )

    beacon_block_queue = receive_server.topic_msg_queues[PUBSUB_TOPIC_BEACON_BLOCK]
    await beacon_block_queue.put(msg)
    # Wait for receive server to process the new block
    await asyncio.sleep(0.5)
    # Check that attestation is removed from attestation pool
    assert attestation not in receive_server.attestation_pool
