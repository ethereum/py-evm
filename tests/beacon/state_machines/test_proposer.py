import pytest

from eth.constants import (
    ZERO_HASH32,
)

from eth.utils.bitfield import (
    has_voted,
)

from eth.beacon.block_proposal import BlockProposal
from eth.beacon.helpers import (
    get_block_committees_info,
)
from eth.beacon.state_machines.validation import (
    validate_parent_block_proposer,
)


@pytest.mark.parametrize(
    (
        'num_validators,'
        'cycle_length,min_committee_size,shard_count'
    ),
    [
        (1000, 20, 10, 100),
    ]
)
def test_propose_block(fixture_sm_class,
                       initial_chaindb,
                       genesis_block,
                       privkeys):
    chaindb = initial_chaindb

    # Propose a block
    block_1_shell = genesis_block.copy(
        parent_hash=genesis_block.hash,
        slot_number=genesis_block.slot_number + 1,
    )
    sm = fixture_sm_class(chaindb, block_1_shell)

    #
    # The proposer of block_1
    #
    block_committees_info = (
        get_block_committees_info(
            block_1_shell,
            sm.crystallized_state,
            sm.config.CYCLE_LENGTH,
        )
    )
    private_key = privkeys[block_committees_info.proposer_index]
    block_proposal = BlockProposal(
        block=block_1_shell,
        shard_id=block_committees_info.proposer_shard_id,
        shard_block_hash=ZERO_HASH32,
    )

    (block_1, post_crystallized_state, post_active_state, proposer_attestation) = (
        sm.propose_block(
            crystallized_state=sm.crystallized_state,
            active_state=sm.active_state,
            block_proposal=block_proposal,
            chaindb=sm.chaindb,
            private_key=private_key,
        )
    )
    expect_block_1 = block_1_shell.copy(
        active_state_root=post_active_state.hash,
        crystallized_state_root=post_crystallized_state.hash,
    )
    assert block_1.hash == expect_block_1.hash

    # Persist block_1
    sm.import_block(block_1)
    sm.chaindb.persist_block(block_1)

    # Validate the attestation
    block_2_shell = block_1.copy(
        parent_hash=block_1.hash,
        slot_number=block_1.slot_number + 1,
        attestations=(proposer_attestation, ),
    )

    # Validate the parent block proposer
    validate_parent_block_proposer(
        sm.crystallized_state,
        block_2_shell,
        block_1,
        sm.config.CYCLE_LENGTH,
    )

    assert has_voted(
        proposer_attestation.attester_bitfield,
        block_committees_info.proposer_index_in_committee
    )

    #
    # The proposer of block_2
    #
    block_committees_info = (
        get_block_committees_info(
            block_2_shell,
            sm.crystallized_state,
            sm.config.CYCLE_LENGTH,
        )
    )
    private_key = privkeys[block_committees_info.proposer_index]
    block_proposal = BlockProposal(
        block=block_2_shell,
        shard_id=block_committees_info.proposer_shard_id,
        shard_block_hash=ZERO_HASH32,
    )

    (block_2, post_crystallized_state, post_active_state, proposer_attestation) = (
        sm.propose_block(
            crystallized_state=sm.crystallized_state,
            active_state=sm.active_state,
            block_proposal=block_proposal,
            chaindb=sm.chaindb,
            private_key=private_key,
        )
    )
    expect_block_2 = block_2_shell.copy(
        active_state_root=post_active_state.hash,
        crystallized_state_root=post_crystallized_state.hash,
    )
    assert block_2.hash == expect_block_2.hash
