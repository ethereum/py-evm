import copy

import pytest


@pytest.fixture
def chain(beacon_chain_without_block_validation):
    return beacon_chain_without_block_validation


@pytest.fixture
def valid_chain(beacon_chain_with_block_validation):
    return beacon_chain_with_block_validation


@pytest.mark.parametrize(
    (
        'num_validators,epoch_length,target_committee_size,shard_count'
    ),
    [
        (100, 20, 10, 10),
    ]
)
def test_canonical_chain(valid_chain):
    genesis_block = valid_chain.get_canonical_block_by_slot(0)

    # Our chain fixture is created with only the genesis header, so initially that's the head of
    # the canonical chain.
    assert valid_chain.get_canonical_head() == genesis_block

    block = genesis_block.copy(
        slot=genesis_block.slot + 1,
        parent_root=genesis_block.root,
    )
    valid_chain.chaindb.persist_block(block, block.__class__)

    assert valid_chain.get_canonical_head() == block

    canonical_block_1 = valid_chain.get_canonical_block_by_slot(
        genesis_block.slot + 1,
    )
    assert canonical_block_1 == block

    result_block = valid_chain.get_block_by_root(block.root)
    assert result_block == block


@pytest.mark.parametrize(
    (
        'num_validators,epoch_length,target_committee_size,shard_count'
    ),
    [
        (100, 20, 10, 10),
    ]
)
def test_import_blocks(valid_chain,
                       create_mock_block,
                       genesis_block,
                       genesis_state,
                       config):
    state = genesis_state
    blocks = tuple()
    for i in range(3):
        block = create_mock_block(
            state=state,
            block_class=genesis_block.__class__,
            parent_block=genesis_block,
            config=config,
            slot=state.slot + 2,
        )

        valid_chain.import_block(block)
        state = valid_chain.get_sm(block).state

        assert block == valid_chain.get_canonical_block_by_slot(
            block.slot
        )
        assert block.root == valid_chain.get_canonical_block_root(
            block.slot
        )
        blocks += (block,)

    valid_chain_2 = copy.deepcopy(valid_chain)
    for block in blocks:
        valid_chain_2.import_block(block)

    assert valid_chain.get_canonical_head() == valid_chain_2.get_canonical_head()
    assert valid_chain.get_sm(blocks[-1]).state == valid_chain_2.get_sm(blocks[-1]).state
