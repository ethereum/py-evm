import pytest

from hypothesis import (
    given,
    strategies as st,
)

import ssz

from eth.constants import (
    GENESIS_PARENT_HASH,
)
from eth.exceptions import (
    BlockNotFound,
    ParentNotFound,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2._utils.ssz import (
    validate_ssz_equal,
)

from eth2.beacon.db.chain import (
    BeaconChainDB,
)
from eth2.beacon.db.schema import SchemaV1
from eth2.beacon.state_machines.forks.serenity.blocks import (
    BeaconBlock,
)
from eth2.beacon.types.states import BeaconState


@pytest.fixture
def chaindb(base_db):
    return BeaconChainDB(base_db)


@pytest.fixture(params=[0, 10, 999])
def block(request, sample_beacon_block_params):
    return BeaconBlock(**sample_beacon_block_params).copy(
        previous_block_root=GENESIS_PARENT_HASH,
        slot=request.param,
    )


@pytest.fixture()
def state(sample_beacon_state_params):
    return BeaconState(**sample_beacon_state_params)


def test_chaindb_add_block_number_to_root_lookup(chaindb, block):
    block_slot_to_root_key = SchemaV1.make_block_slot_to_root_lookup_key(block.slot)
    assert not chaindb.exists(block_slot_to_root_key)
    chaindb.persist_block(block, block.__class__)
    assert chaindb.exists(block_slot_to_root_key)


def test_chaindb_persist_block_and_slot_to_root(chaindb, block):
    with pytest.raises(BlockNotFound):
        chaindb.get_block_by_root(block.signing_root, block.__class__)
    slot_to_root_key = SchemaV1.make_block_root_to_score_lookup_key(block.signing_root)
    assert not chaindb.exists(slot_to_root_key)

    chaindb.persist_block(block, block.__class__)

    assert chaindb.get_block_by_root(block.signing_root, block.__class__) == block
    assert chaindb.exists(slot_to_root_key)


@given(seed=st.binary(min_size=32, max_size=32))
def test_chaindb_persist_block_and_unknown_parent(chaindb, block, seed):
    n_block = block.copy(previous_block_root=hash_eth2(seed))
    with pytest.raises(ParentNotFound):
        chaindb.persist_block(n_block, n_block.__class__)


def test_chaindb_persist_block_and_block_to_root(chaindb, block):
    block_to_root_key = SchemaV1.make_block_root_to_score_lookup_key(block.signing_root)
    assert not chaindb.exists(block_to_root_key)
    chaindb.persist_block(block, block.__class__)
    assert chaindb.exists(block_to_root_key)


def test_chaindb_get_score(chaindb, sample_beacon_block_params):
    genesis = BeaconBlock(**sample_beacon_block_params).copy(
        previous_block_root=GENESIS_PARENT_HASH,
        slot=0,
    )
    chaindb.persist_block(genesis, genesis.__class__)

    genesis_score_key = SchemaV1.make_block_root_to_score_lookup_key(genesis.signing_root)
    genesis_score = ssz.decode(chaindb.db.get(genesis_score_key), sedes=ssz.sedes.uint64)
    assert genesis_score == 0
    assert chaindb.get_score(genesis.signing_root) == 0

    block1 = BeaconBlock(**sample_beacon_block_params).copy(
        previous_block_root=genesis.signing_root,
        slot=1,
    )
    chaindb.persist_block(block1, block1.__class__)

    block1_score_key = SchemaV1.make_block_root_to_score_lookup_key(block1.signing_root)
    block1_score = ssz.decode(chaindb.db.get(block1_score_key), sedes=ssz.sedes.uint64)
    assert block1_score == 1
    assert chaindb.get_score(block1.signing_root) == 1


def test_chaindb_get_block_by_root(chaindb, block):
    chaindb.persist_block(block, block.__class__)
    result_block = chaindb.get_block_by_root(block.signing_root, block.__class__)
    validate_ssz_equal(result_block, block)


def test_chaindb_get_canonical_block_root(chaindb, block):
    chaindb.persist_block(block, block.__class__)
    block_root = chaindb.get_canonical_block_root(block.slot)
    assert block_root == block.signing_root


def test_chaindb_state(chaindb, state):
    chaindb.persist_state(state)
    state_class = BeaconState
    result_state = chaindb.get_state_by_root(state.root, state_class)
    assert result_state.root == state.root


def test_chaindb_get_finalized_head(chaindb, block):
    # TODO: update when we support finalizing blocks that are not the genesis block
    genesis = block.copy(previous_block_root=GENESIS_PARENT_HASH)
    chaindb.persist_block(genesis, BeaconBlock)
    assert chaindb.get_finalized_head(BeaconBlock) == genesis


def test_chaindb_get_canonical_head(chaindb, block):
    chaindb.persist_block(block, block.__class__)

    canonical_head_root = chaindb.get_canonical_head_root()
    assert canonical_head_root == block.signing_root

    result_block = chaindb.get_canonical_head(block.__class__)
    assert result_block == block

    block_2 = block.copy(
        slot=block.slot + 1,
        previous_block_root=block.signing_root,
    )
    chaindb.persist_block(block_2, block_2.__class__)
    result_block = chaindb.get_canonical_head(block.__class__)
    assert result_block == block_2

    block_3 = block.copy(
        slot=block_2.slot + 1,
        previous_block_root=block_2.signing_root,
    )
    chaindb.persist_block(block_3, block_3.__class__)
    result_block = chaindb.get_canonical_head(block.__class__)
    assert result_block == block_3


def test_get_slot_by_root(chaindb, block):
    chaindb.persist_block(block, block.__class__)
    block_slot = block.slot
    result_slot = chaindb.get_slot_by_root(block.signing_root)
    assert result_slot == block_slot
