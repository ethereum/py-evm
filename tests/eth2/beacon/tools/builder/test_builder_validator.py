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
    get_next_epoch_committee_assignment,
    verify_votes,
)


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
    message = b'hello'

    # Get votes: (committee_index, sig, public_key)
    votes = [
        (
            committee_index,
            bls.sign(message, privkeys[committee_index], domain),
            pubkeys[committee_index],
        )
        for committee_index in random_votes
    ]

    # Verify
    sigs, committee_indices = verify_votes(message, votes, domain)

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
    assert bls.verify(message, aggregated_pubs, sigs, domain)


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'registry_change,'
    ),
    [
        (40, 16, 1, 2, True),
        (40, 16, 1, 2, False),
    ]
)
def test_get_next_epoch_committee_assignment(genesis_state,
                                             epoch_length,
                                             shard_count,
                                             config,
                                             num_validators,
                                             registry_change):
    state = genesis_state
    proposer_count = 0
    shard_validator_count = [
        0
        for _ in range(shard_count)
    ]
    slots = []
    next_epoch_start = get_epoch_start_slot(state.current_epoch(epoch_length) + 1, epoch_length)

    for validator_index in range(num_validators):
        assignment = get_next_epoch_committee_assignment(
            state,
            config,
            validator_index,
            registry_change,
        )
        assert assignment.slot >= next_epoch_start
        assert assignment.slot < next_epoch_start + epoch_length
        if assignment.is_proposer:
            proposer_count += 1

        shard_validator_count[assignment.shard] += 1
        slots.append(assignment.slot)

    assert proposer_count == epoch_length
    assert sum(shard_validator_count) == num_validators


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
    ),
    [
        (40, 16, 1, 2),
    ]
)
def test_get_next_epoch_committee_assignment_no_assignment(genesis_state,
                                                           genesis_epoch,
                                                           config):
    state = genesis_state
    validator_index = 1
    state = state.update_validator_registry(
        validator_index,
        validator=state.validator_registry[validator_index].copy(
            exit_epoch=genesis_epoch,
        )
    )

    with pytest.raises(NoCommitteeAssignment):
        get_next_epoch_committee_assignment(state, config, validator_index, True)
