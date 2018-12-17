import pytest

from hypothesis import (
    given,
    strategies as st,
)

import rlp

from eth.constants import (
    GENESIS_PARENT_HASH,
)
from eth.exceptions import (
    BlockNotFound,
    ParentNotFound,
)
from eth.beacon.utils.hash import (
    hash_,
)
from eth.utils.rlp import (
    validate_rlp_equal,
)

from eth.beacon.db.chain import (
    BeaconChainDB,
)
from eth.beacon.db.schema import SchemaV1
from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.states import BeaconState


@pytest.fixture
def chaindb(base_db):
    return BeaconChainDB(base_db)


@pytest.fixture(params=[0, 10, 999])
def block(request, sample_beacon_block_params):
    return BaseBeaconBlock(**sample_beacon_block_params).copy(
        parent_root=GENESIS_PARENT_HASH,
        slot=request.param,
    )


@pytest.fixture()
def state(sample_beacon_state_params):
    return BeaconState(**sample_beacon_state_params)


def test_chaindb_add_block_number_to_root_lookup(chaindb, block):
    block_slot_to_root_key = SchemaV1.make_block_slot_to_root_lookup_key(block.slot)
    assert not chaindb.exists(block_slot_to_root_key)
    chaindb.persist_block(block)
    assert chaindb.exists(block_slot_to_root_key)


def test_chaindb_persist_block_and_slot_to_root(chaindb, block):
    with pytest.raises(BlockNotFound):
        chaindb.get_block_by_root(block.root)
    slot_to_root_key = SchemaV1.make_block_root_to_score_lookup_key(block.root)
    assert not chaindb.exists(slot_to_root_key)

    chaindb.persist_block(block)

    assert chaindb.get_block_by_root(block.root) == block
    assert chaindb.exists(slot_to_root_key)


@given(seed=st.binary(min_size=32, max_size=32))
def test_chaindb_persist_block_and_unknown_parent(chaindb, block, seed):
    n_block = block.copy(parent_root=hash_(seed))
    with pytest.raises(ParentNotFound):
        chaindb.persist_block(n_block)


def test_chaindb_persist_block_and_block_to_root(chaindb, block):
    block_to_root_key = SchemaV1.make_block_root_to_score_lookup_key(block.root)
    assert not chaindb.exists(block_to_root_key)
    chaindb.persist_block(block)
    assert chaindb.exists(block_to_root_key)


def test_chaindb_get_score(chaindb, sample_beacon_block_params):
    genesis = BaseBeaconBlock(**sample_beacon_block_params).copy(
        parent_root=GENESIS_PARENT_HASH,
        slot=0,
    )
    chaindb.persist_block(genesis)

    genesis_score_key = SchemaV1.make_block_root_to_score_lookup_key(genesis.root)
    genesis_score = rlp.decode(chaindb.db.get(genesis_score_key), sedes=rlp.sedes.big_endian_int)
    assert genesis_score == 0
    assert chaindb.get_score(genesis.root) == 0

    block1 = BaseBeaconBlock(**sample_beacon_block_params).copy(
        parent_root=genesis.root,
        slot=1,
    )
    chaindb.persist_block(block1)

    block1_score_key = SchemaV1.make_block_root_to_score_lookup_key(block1.root)
    block1_score = rlp.decode(chaindb.db.get(block1_score_key), sedes=rlp.sedes.big_endian_int)
    assert block1_score == 1
    assert chaindb.get_score(block1.root) == 1


def test_chaindb_get_block_by_root(chaindb, block):
    chaindb.persist_block(block)
    result_block = chaindb.get_block_by_root(block.root)
    validate_rlp_equal(result_block, block)


def test_chaindb_get_canonical_block_root(chaindb, block):
    chaindb.persist_block(block)
    block_root = chaindb.get_canonical_block_root(block.slot)
    assert block_root == block.root


def test_chaindb_state(chaindb, state):
    chaindb.persist_state(state)

    result_state = chaindb.get_state_by_root(state.root)
    assert result_state.root == state.root
