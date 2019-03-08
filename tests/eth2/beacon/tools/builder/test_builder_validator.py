import pytest
from hypothesis import (
    given,
    settings,
    strategies as st,
)

from eth2._utils import bls
from eth2._utils.bitfield import (
    get_empty_bitfield,
    has_voted,
)
from eth2.beacon.exceptions import (
    NoCommitteeAssignment,
)
from eth2.beacon.helpers import (
    get_epoch_start_slot,
)

from eth2.beacon.tools.builder.validator import (
    aggregate_votes,
    get_committee_assignment,
    verify_votes,
)


@pytest.mark.slow
@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'votes_count'
    ),
    [
        (0),
        (9),
    ],
)
def test_aggregate_votes(votes_count, random, privkeys, pubkeys):
    bit_count = 10
    pre_bitfield = get_empty_bitfield(bit_count)
    pre_sigs = ()
    domain = 0

    random_votes = random.sample(range(bit_count), votes_count)
    message_hash = b'\x12' * 32

    # Get votes: (committee_index, sig, public_key)
    votes = [
        (
            committee_index,
            bls.sign(message_hash, privkeys[committee_index], domain),
            pubkeys[committee_index],
        )
        for committee_index in random_votes
    ]

    # Verify
    sigs, committee_indices = verify_votes(message_hash, votes, domain)

    # Aggregate the votes
    bitfield, sigs = aggregate_votes(
        bitfield=pre_bitfield,
        sigs=pre_sigs,
        voting_sigs=sigs,
        voting_committee_indices=committee_indices
    )

    try:
        _, _, pubs = zip(*votes)
    except ValueError:
        pubs = ()

    voted_index = [
        committee_index
        for committee_index in random_votes
        if has_voted(bitfield, committee_index)
    ]
    assert len(voted_index) == len(votes)

    aggregated_pubs = bls.aggregate_pubkeys(pubs)
    assert bls.verify(message_hash, aggregated_pubs, sigs, domain)


@pytest.mark.parametrize(
    (
        'registry_change'
    ),
    [
        (True),
        (False),
    ]

)
@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'state_epoch,'
        'epoch,'
        'genesis_slot,'
    ),
    [
        (40, 16, 1, 2, 0, 0, 0),  # genesis
        (40, 16, 1, 2, 1, 1, 0),  # current epoch
        (40, 16, 1, 2, 1, 0, 0),  # previous epoch
        (40, 16, 1, 2, 1, 2, 0),  # next epoch
    ]
)
def test_get_committee_assignment(genesis_state,
                                  slots_per_epoch,
                                  shard_count,
                                  config,
                                  num_validators,
                                  state_epoch,
                                  epoch,
                                  registry_change):
    state_slot = get_epoch_start_slot(state_epoch, slots_per_epoch)
    state = genesis_state.copy(
        slot=state_slot,
    )
    proposer_count = 0
    shard_validator_count = [
        0
        for _ in range(shard_count)
    ]
    slots = []

    epoch_start_slot = get_epoch_start_slot(epoch, slots_per_epoch)

    for validator_index in range(num_validators):
        assignment = get_committee_assignment(
            state,
            config,
            epoch,
            validator_index,
            registry_change,
        )
        assert assignment.slot >= epoch_start_slot
        assert assignment.slot < epoch_start_slot + slots_per_epoch
        if assignment.is_proposer:
            proposer_count += 1

        shard_validator_count[assignment.shard] += 1
        slots.append(assignment.slot)

    assert proposer_count == slots_per_epoch
    assert sum(shard_validator_count) == num_validators


@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
    ),
    [
        (40, 16, 1, 2),
    ]
)
def test_get_committee_assignment_no_assignment(genesis_state,
                                                genesis_epoch,
                                                slots_per_epoch,
                                                config):
    state = genesis_state
    validator_index = 1
    current_epoch = state.current_epoch(slots_per_epoch)
    validator = state.validator_registry[validator_index].copy(
        exit_epoch=genesis_epoch,
    )
    state = state.update_validator_registry(
        validator_index,
        validator=validator,
    )
    assert not validator.is_active(current_epoch)

    with pytest.raises(NoCommitteeAssignment):
        get_committee_assignment(state, config, current_epoch, validator_index, True)
