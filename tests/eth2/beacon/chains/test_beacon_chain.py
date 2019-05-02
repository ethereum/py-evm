import copy

import pytest


from eth2.beacon.chains.base import (
    BeaconChain,
)
from eth2.beacon.exceptions import (
    BlockClassError,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.tools.builder.proposer import (
    create_mock_block,
)
from eth2.beacon.types.blocks import (
    BeaconBlock,
)


@pytest.fixture
def chain(beacon_chain_without_block_validation):
    return beacon_chain_without_block_validation


@pytest.fixture
def valid_chain(beacon_chain_with_block_validation):
    return beacon_chain_with_block_validation


@pytest.mark.parametrize(
    (
        'num_validators,slots_per_epoch,target_committee_size,shard_count'
    ),
    [
        (100, 20, 10, 10),
    ]
)
def test_canonical_chain(valid_chain, genesis_slot):
    genesis_block = valid_chain.get_canonical_block_by_slot(genesis_slot)

    # Our chain fixture is created with only the genesis header, so initially that's the head of
    # the canonical chain.
    assert valid_chain.get_canonical_head() == genesis_block

    block = genesis_block.copy(
        slot=genesis_block.slot + 1,
        previous_block_root=genesis_block.signing_root,
    )
    valid_chain.chaindb.persist_block(block, block.__class__)

    assert valid_chain.get_canonical_head() == block

    canonical_block_1 = valid_chain.get_canonical_block_by_slot(
        genesis_block.slot + 1,
    )
    assert canonical_block_1 == block

    result_block = valid_chain.get_block_by_root(block.signing_root)
    assert result_block == block


@pytest.mark.long
@pytest.mark.parametrize(
    (
        'num_validators,slots_per_epoch,target_committee_size,shard_count'
    ),
    [
        (100, 16, 10, 10),
    ]
)
def test_import_blocks(valid_chain,
                       genesis_block,
                       genesis_state,
                       config,
                       keymap):
    state = genesis_state
    blocks = (genesis_block,)
    valid_chain_2 = copy.deepcopy(valid_chain)
    for _ in range(3):
        block = create_mock_block(
            state=state,
            config=config,
            state_machine=valid_chain.get_state_machine(blocks[-1]),
            block_class=genesis_block.__class__,
            parent_block=blocks[-1],
            keymap=keymap,
            slot=state.slot + 2,
        )

        valid_chain.import_block(block)
        assert valid_chain.get_canonical_head() == block

        state = valid_chain.get_state_machine(block).state

        assert block == valid_chain.get_canonical_block_by_slot(
            block.slot
        )
        assert block.signing_root == valid_chain.get_canonical_block_root(
            block.slot
        )
        blocks += (block,)

    assert valid_chain.get_canonical_head() != valid_chain_2.get_canonical_head()

    for block in blocks[1:]:
        valid_chain_2.import_block(block)

    assert valid_chain.get_canonical_head() == valid_chain_2.get_canonical_head()
    assert valid_chain.get_state_machine(blocks[-1]).state.slot != 0
    assert (
        valid_chain.get_state_machine(blocks[-1]).state ==
        valid_chain_2.get_state_machine(blocks[-1]).state
    )


def test_from_genesis(base_db,
                      genesis_block,
                      genesis_state,
                      fixture_sm_class):
    klass = BeaconChain.configure(
        __name__='TestChain',
        sm_configuration=(
            (0, fixture_sm_class),
        ),
        chain_id=5566,
    )

    assert type(genesis_block) == SerenityBeaconBlock
    block = BeaconBlock.convert_block(genesis_block)
    assert type(block) == BeaconBlock

    with pytest.raises(BlockClassError):
        klass.from_genesis(
            base_db,
            genesis_state,
            block,
        )
