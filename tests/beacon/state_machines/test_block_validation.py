import pytest

from eth_utils import (
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth.utils.bitfield import (
    get_empty_bitfield,
    set_voted,
)

from eth.beacon.block_proposal import BlockProposal
from eth.beacon.state_machines.validation import (
    validate_aggregate_sig,
    validate_attestation,
    validate_bitfield,
    validate_justified,
    validate_parent_block_proposer,
    validate_slot,
    validate_state_roots,
)


from eth.beacon.helpers import (
    get_attestation_indices,
    get_block_committees_info,
    get_new_recent_block_hashes,
    get_signed_parent_hashes,
)


@pytest.fixture
def attestation_validation_fixture(fixture_sm_class,
                                   initial_chaindb,
                                   genesis_block,
                                   privkeys):
    # NOTE: Copied from `test_proposer.py`, might need to refactor it.

    chaindb = initial_chaindb

    # Propose a block
    block_1_shell = genesis_block.copy(
        parent_hash=genesis_block.hash,
        slot_number=genesis_block.slot_number + 1,
    )
    sm = fixture_sm_class(chaindb, block_1_shell)

    # The proposer of block_1
    block_committees_info = (
        get_block_committees_info(
            block_1_shell,
            sm.crystallized_state,
            sm.config.CYCLE_LENGTH,
        )
    )
    # public_key = sm.crystallized_state.validators[block_committees_info.proposer_index].pubkey
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
            config=sm.config,
            private_key=private_key,
        )
    )

    # Block 2
    # Manually update state for testing
    sm._update_the_states(post_crystallized_state, post_active_state)

    # Validate the attestation
    block_2_shell = block_1.copy(
        parent_hash=block_1.hash,
        slot_number=block_1.slot_number + 1,
        attestations=[proposer_attestation],
    )
    recent_block_hashes = get_new_recent_block_hashes(
        sm.active_state.recent_block_hashes,
        block_1.slot_number,
        block_2_shell.slot_number,
        block_1.hash
    )
    filled_active_state = sm.active_state.copy(
        recent_block_hashes=recent_block_hashes,
    )

    return (
        post_crystallized_state,
        filled_active_state,
        proposer_attestation,
        block_2_shell,
        block_1,
        sm.chaindb
    )


@pytest.mark.parametrize(
    (
        'num_validators,cycle_length,'
        'min_committee_size,shard_count'
    ),
    [
        (100, 50, 10, 10)
    ],
)
def test_validate_parent_block_proposer(attestation_validation_fixture,
                                        cycle_length):
    (
        crystallized_state,
        _,
        attestation,
        block,
        parent_block,
        _,
    ) = attestation_validation_fixture

    validate_parent_block_proposer(
        crystallized_state,
        block,
        parent_block,
        cycle_length,
    )

    # Case 1: No attestations
    block = block.copy(
        attestations=()
    )
    with pytest.raises(ValidationError):
        validate_parent_block_proposer(
            crystallized_state,
            block,
            parent_block,
            cycle_length,
        )

    # Case 2: Proposer didn't attest
    block = block.copy(
        attestations=[
            attestation.copy(
                attester_bitfield=get_empty_bitfield(10),
            )
        ]
    )
    with pytest.raises(ValidationError):
        validate_parent_block_proposer(
            crystallized_state,
            block,
            parent_block,
            cycle_length,
        )


@pytest.mark.parametrize(
    (
        'num_validators,cycle_length,'
        'min_committee_size,shard_count'
    ),
    [
        (100, 50, 10, 10),
    ],
)
def test_validate_attestation_valid(attestation_validation_fixture, cycle_length):
    (
        crystallized_state,
        active_state,
        attestation,
        block,
        parent_block,
        chaindb,
    ) = attestation_validation_fixture

    validate_attestation(
        block,
        parent_block,
        crystallized_state,
        active_state.recent_block_hashes,
        attestation,
        chaindb,
        cycle_length,
    )


@pytest.mark.parametrize(
    (
        'num_validators,cycle_length,'
        'min_committee_size,shard_count,'
        'attestation_slot'
    ),
    [
        (100, 50, 10, 10, 2),
        (100, 50, 10, 10, -1),
    ],
)
def test_validate_slot(attestation_validation_fixture, cycle_length, attestation_slot):
    (
        _,
        _,
        attestation,
        _,
        parent_block,
        _,
    ) = attestation_validation_fixture

    attestation = attestation.copy(
        slot=attestation_slot,
    )
    with pytest.raises(ValidationError):
        validate_slot(
            parent_block=parent_block,
            attestation=attestation,
            cycle_length=cycle_length,
        )


@pytest.mark.parametrize(
    (
        'num_validators,cycle_length,'
        'min_committee_size,shard_count,'
    ),
    [
        (100, 50, 10, 10),
    ],
)
def test_validate_justified(attestation_validation_fixture):
    (
        crystallized_state,
        _,
        attestation,
        _,
        _,
        chaindb,
    ) = attestation_validation_fixture

    # Case 1: attestation.justified_slot > crystallized_state.last_justified_slot
    attestation_case_1 = attestation.copy(
        justified_slot=crystallized_state.last_justified_slot + 1
    )
    with pytest.raises(ValidationError):
        validate_justified(
            crystallized_state,
            attestation_case_1,
            chaindb,
        )

    # Case 2: justified_block_hash is not in canonical chain
    attestation_case_2 = attestation.copy(
        justified_block_hash=b'\x11' * 32
    )
    with pytest.raises(ValidationError):
        validate_justified(
            crystallized_state,
            attestation_case_2,
            chaindb,
        )

    # Case 3: justified_slot doesn't match justified_block_hash
    attestation_case_3 = attestation.copy(
        justified_slot=attestation.justified_slot - 1
    )
    with pytest.raises(ValidationError):
        validate_justified(
            crystallized_state,
            attestation_case_3,
            chaindb,
        )


@pytest.mark.parametrize(
    (
        'num_validators,cycle_length,'
        'min_committee_size,shard_count'
    ),
    [
        (100, 50, 10, 10),
    ],
)
def test_validate_bitfield(attestation_validation_fixture, cycle_length):
    (
        crystallized_state,
        _,
        attestation,
        _,
        _,
        _,
    ) = attestation_validation_fixture

    attestation_indices = get_attestation_indices(
        crystallized_state,
        attestation,
        cycle_length,
    )

    # Case 1: Attestation has incorrect bitfield length
    attestation_case_1 = attestation.copy(
        attester_bitfield=get_empty_bitfield(10),
    )
    with pytest.raises(ValidationError):
        validate_bitfield(
            attestation_case_1,
            attestation_indices
        )

    # Case 2: End bits are not all zero
    last_bit = len(attestation_indices)
    attestation_case_2 = attestation.copy(
        attester_bitfield=set_voted(attestation.attester_bitfield, last_bit),
    )
    with pytest.raises(ValidationError):
        validate_bitfield(
            attestation_case_2,
            attestation_indices
        )


@pytest.mark.parametrize(
    (
        'num_validators,cycle_length,'
        'min_committee_size,shard_count'
    ),
    [
        (100, 50, 10, 10),
    ],
)
def test_validate_attestation_aggregate_sig(attestation_validation_fixture, cycle_length):
    (
        crystallized_state,
        active_state,
        attestation,
        block,
        _,
        _
    ) = attestation_validation_fixture

    attestation_indices = get_attestation_indices(
        crystallized_state,
        attestation,
        cycle_length,
    )
    parent_hashes = get_signed_parent_hashes(
        active_state.recent_block_hashes,
        block,
        attestation,
        cycle_length,
    )

    attestation = attestation.copy(
        aggregate_sig=[0, 0]
    )
    with pytest.raises(ValidationError):
        validate_aggregate_sig(
            crystallized_state,
            attestation,
            attestation_indices,
            parent_hashes,
        )


def test_validate_state_roots(genesis_crystallized_state, genesis_active_state, genesis_block):

    validate_state_roots(
        crystallized_state_root=genesis_crystallized_state.hash,
        active_state_root=genesis_active_state.hash,
        block=genesis_block,
    )

    # Case 1: Wrong crystallized state root
    with pytest.raises(ValidationError):
        validate_state_roots(
            crystallized_state_root=genesis_active_state,
            active_state_root=genesis_active_state.hash,
            block=genesis_block.copy(
                active_state_root=ZERO_HASH32,
            ),
        )

    with pytest.raises(ValidationError):
        validate_state_roots(
            crystallized_state_root=genesis_active_state,
            active_state_root=genesis_active_state.hash,
            block=genesis_block.copy(
                crystallized_state_root=ZERO_HASH32,
            ),
        )
