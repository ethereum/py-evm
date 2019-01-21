import copy
import random

import itertools
import pytest

from hypothesis import (
    given,
    strategies as st,
)

from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import assoc

from eth.constants import (
    ZERO_HASH32,
)
from eth2.beacon.constants import (
    GWEI_PER_ETH,
    FAR_FUTURE_SLOT,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.types.attestation_data import (
    AttestationData,
)
from eth2.beacon.types.fork_data import ForkData
from eth2.beacon.types.crosslink_committees import CrosslinkCommittee
from eth2.beacon.types.slashable_vote_data import SlashableVoteData
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validator_records import ValidatorRecord
from eth2.beacon.helpers import (
    _get_block_root,
    _get_crosslink_committees_at_slot,
    get_active_validator_indices,
    get_attestation_participants,
    get_beacon_proposer_index,
    get_effective_balance,
    get_domain,
    get_fork_version,
    get_shuffling,
    get_block_committees_info,
    get_pubkey_for_indices,
    generate_aggregate_pubkeys,
    verify_vote_count,
    verify_slashable_vote_data_signature,
    verify_slashable_vote_data,
    is_double_vote,
    is_surround_vote,
)
import eth2._utils.bls as bls

from tests.eth2.beacon.helpers import (
    get_pseudo_chain,
)


@pytest.fixture()
def sample_block(sample_beacon_block_params):
    return SerenityBeaconBlock(**sample_beacon_block_params)


@pytest.fixture()
def sample_state(sample_beacon_state_params):
    return BeaconState(**sample_beacon_state_params)


def get_sample_crosslink_committees_at_slots(num_slot,
                                             num_crosslink_committee_per_slot,
                                             sample_crosslink_committee_params):

    return tuple(
        [
            [
                CrosslinkCommittee(**sample_crosslink_committee_params)
                for _ in range(num_crosslink_committee_per_slot)
            ]
            for _ in range(num_slot)
        ]
    )


def generate_mock_latest_block_roots(
        genesis_block,
        current_slot,
        epoch_length,
        latest_block_roots_length):
    assert current_slot < latest_block_roots_length

    chain_length = (current_slot // epoch_length + 1) * epoch_length
    blocks = get_pseudo_chain(chain_length, genesis_block)
    latest_block_roots = [
        block.hash
        for block in blocks[:current_slot]
    ] + [
        ZERO_HASH32
        for _ in range(latest_block_roots_length - current_slot)
    ]
    return blocks, latest_block_roots


#
# Get block rootes
#
@pytest.mark.parametrize(
    (
        'current_slot,target_slot,success'
    ),
    [
        (10, 0, True),
        (10, 9, True),
        (10, 10, False),
        (128, 0, True),
        (128, 127, True),
        (128, 128, False),
    ],
)
def test_get_block_root(current_slot,
                        target_slot,
                        success,
                        epoch_length,
                        latest_block_roots_length,
                        sample_block):
    blocks, latest_block_roots = generate_mock_latest_block_roots(
        sample_block,
        current_slot,
        epoch_length,
        latest_block_roots_length,
    )

    if success:
        block_root = _get_block_root(
            latest_block_roots,
            current_slot,
            target_slot,
            latest_block_roots_length,
        )
        assert block_root == blocks[target_slot].root
    else:
        with pytest.raises(ValidationError):
            _get_block_root(
                latest_block_roots,
                current_slot,
                target_slot,
                latest_block_roots_length,
            )


#
# Get crosslinks_committees or indices
#
@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'state_slot,'
        'num_slot,'
        'num_crosslink_committee_per_slot,'
        'slot,'
        'success'
    ),
    [
        (
            100,
            64,
            0,
            128,
            10,
            0,
            True,
        ),
        (
            100,
            64,
            64,
            128,
            10,
            64,
            True,
        ),
        (
            100,
            64,
            1,
            128,
            10,
            1,
            True,
        ),
        # slot is too small
        (
            100,
            64,
            128,
            128,
            10,
            0,
            False,
        ),
        # slot is too large
        (
            100,
            64,
            0,
            128,
            10,
            64,
            False,
        ),
    ],
)
def test_get_crosslink_committees_at_slot(
        num_validators,
        epoch_length,
        state_slot,
        num_slot,
        num_crosslink_committee_per_slot,
        slot,
        success,
        sample_crosslink_committee_params):

    crosslink_committees_at_slots = get_sample_crosslink_committees_at_slots(
        num_slot,
        num_crosslink_committee_per_slot,
        sample_crosslink_committee_params
    )

    if success:
        crosslink_committees = _get_crosslink_committees_at_slot(
            state_slot=state_slot,
            crosslink_committees_at_slots=crosslink_committees_at_slots,
            slot=slot,
            epoch_length=epoch_length,
        )
        assert len(crosslink_committees) > 0
        assert len(crosslink_committees[0].committee) > 0
    else:
        with pytest.raises(ValidationError):
            _get_crosslink_committees_at_slot(
                state_slot=state_slot,
                crosslink_committees_at_slots=crosslink_committees_at_slots,
                slot=slot,
                epoch_length=epoch_length,
            )


#
# Shuffling
#
@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'slot'
    ),
    [
        (1000, 20, 10, 100, 0),
        (1000, 20, 10, 100, 5),
        (1000, 20, 10, 100, 30),
        (20, 10, 3, 10, 0),  # active_validators_size < epoch_length * target_committee_size
        (20, 10, 3, 10, 5),
        (20, 10, 3, 10, 30),
    ],
)
def test_get_shuffling_is_complete(activated_genesis_validators,
                                   epoch_length,
                                   target_committee_size,
                                   shard_count,
                                   slot):
    shuffling = get_shuffling(
        seed=b'\x35' * 32,
        validators=activated_genesis_validators,
        crosslinking_start_shard=0,
        slot=slot,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    assert len(shuffling) == epoch_length
    validators = set()
    shards = set()
    for slot_indices in shuffling:
        for crosslink_committee in slot_indices:
            shards.add(crosslink_committee.shard)
            for validator_index in crosslink_committee.committee:
                validators.add(validator_index)

    assert len(activated_genesis_validators) > 0
    assert len(validators) == len(activated_genesis_validators)


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count'
    ),
    [
        (1000, 20, 10, 100),
        (100, 50, 10, 10),
        (20, 10, 3, 10),
    ],
)
def test_get_shuffling_handles_shard_wrap(activated_genesis_validators,
                                          epoch_length,
                                          target_committee_size,
                                          shard_count):
    shuffling = get_shuffling(
        seed=b'\x35' * 32,
        validators=activated_genesis_validators,
        crosslinking_start_shard=shard_count - 1,
        slot=0,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    # shard assignments should wrap around to 0 rather than continuing to SHARD_COUNT
    for slot_indices in shuffling:
        for crosslink_committee in slot_indices:
            assert crosslink_committee.shard < shard_count


#
# Get proposer postition
#
@pytest.mark.parametrize(
    (
        'num_validators,committee,parent_block_number,result_proposer_index'
    ),
    [
        (100, [4, 5, 6, 7], 0, 4),
        (100, [4, 5, 6, 7], 2, 6),
        (100, [4, 5, 6, 7], 11, 7),
        (100, [], 1, ValidationError()),
    ],
)
def test_get_block_committees_info(monkeypatch,
                                   sample_block,
                                   sample_state,
                                   num_validators,
                                   committee,
                                   parent_block_number,
                                   result_proposer_index,
                                   epoch_length):
    from eth2.beacon import helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              epoch_length):
        return (
            CrosslinkCommittee(
                shard=1,
                committee=committee,
                total_validator_count=num_validators,
            ),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    parent_block = sample_block
    parent_block = sample_block.copy(
        slot=parent_block_number,
    )

    if isinstance(result_proposer_index, Exception):
        with pytest.raises(ValidationError):
            get_block_committees_info(
                parent_block,
                sample_state,
                epoch_length,
            )
    else:
        block_committees_info = get_block_committees_info(
            parent_block,
            sample_state,
            epoch_length,
        )
        assert (
            block_committees_info.proposer_index ==
            result_proposer_index
        )


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'committee,'
        'slot,'
        'success,'
    ),
    [
        (
            100,
            64,
            (10, 11, 12),
            0,
            True,
        ),
        (
            100,
            64,
            (),
            0,
            False,
        ),
    ]
)
def test_get_beacon_proposer_index(
        monkeypatch,
        num_validators,
        epoch_length,
        committee,
        slot,
        success,
        sample_state):

    from eth2.beacon import helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              epoch_length):
        return (
            CrosslinkCommittee(
                shard=1,
                committee=committee,
                total_validator_count=num_validators,
            ),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )
    if success:
        proposer_index = get_beacon_proposer_index(
            sample_state,
            slot,
            epoch_length
        )
        assert proposer_index == committee[slot % len(committee)]
    else:
        with pytest.raises(ValidationError):
            get_beacon_proposer_index(
                sample_state,
                slot,
                epoch_length
            )


def test_get_active_validator_indices(sample_validator_record_params):
    current_slot = 1
    # 3 validators are ACTIVE
    validators = [
        ValidatorRecord(
            **sample_validator_record_params,
        ).copy(
            activation_slot=0,
            exit_slot=FAR_FUTURE_SLOT,
        )
        for i in range(3)
    ]
    active_validator_indices = get_active_validator_indices(validators, current_slot)
    assert len(active_validator_indices) == 3

    validators[0] = validators[0].copy(
        activation_slot=current_slot + 1,  # activation_slot > current_slot
    )
    active_validator_indices = get_active_validator_indices(validators, current_slot)
    assert len(active_validator_indices) == 2


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'committee,'
        'participation_bitfield,'
        'expected'
    ),
    [
        (
            100,
            64,
            (10, 11, 12),
            b'\00',
            (),
        ),
        (
            100,
            64,
            (10, 11, 12),
            b'\x80',
            (10,),
        ),
        (
            100,
            64,
            (10, 11, 12),
            b'\xc0',
            (10, 11),
        ),
        (
            100,
            64,
            (10, 11, 12),
            b'\x00\x00',
            ValueError(),
        ),
    ]
)
def test_get_attestation_participants(
        monkeypatch,
        num_validators,
        epoch_length,
        committee,
        participation_bitfield,
        expected,
        sample_state):
    from eth2.beacon import helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              epoch_length):
        return (
            CrosslinkCommittee(
                shard=0,
                committee=committee,
                total_validator_count=num_validators,
            ),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    if isinstance(expected, Exception):
        with pytest.raises(ValidationError):
            get_attestation_participants(
                state=sample_state,
                slot=0,
                shard=0,
                participation_bitfield=participation_bitfield,
                epoch_length=epoch_length,
            )
    else:
        result = get_attestation_participants(
            state=sample_state,
            slot=0,
            shard=0,
            participation_bitfield=participation_bitfield,
            epoch_length=epoch_length,
        )

        assert result == expected


@pytest.mark.parametrize(
    (
        'balance,'
        'max_deposit,'
        'expected'
    ),
    [
        (
            1 * GWEI_PER_ETH,
            32,
            1 * GWEI_PER_ETH,
        ),
        (
            32 * GWEI_PER_ETH,
            32,
            32 * GWEI_PER_ETH,
        ),
        (
            33 * GWEI_PER_ETH,
            32,
            32 * GWEI_PER_ETH,
        )
    ]
)
def test_get_effective_balance(balance, max_deposit, expected, sample_validator_record_params):
    balances = (balance,)
    result = get_effective_balance(balances, 0, max_deposit)
    assert result == expected


@pytest.mark.parametrize(
    (
        'pre_fork_version,'
        'post_fork_version,'
        'fork_slot,'
        'current_slot,'
        'expected'
    ),
    [
        (0, 0, 0, 0, 0),
        (0, 0, 0, 1, 0),
        (0, 1, 20, 10, 0),
        (0, 1, 20, 20, 1),
        (0, 1, 10, 20, 1),
    ]
)
def test_get_fork_version(pre_fork_version,
                          post_fork_version,
                          fork_slot,
                          current_slot,
                          expected):
    fork_data = ForkData(
        pre_fork_version=pre_fork_version,
        post_fork_version=post_fork_version,
        fork_slot=fork_slot,
    )
    assert expected == get_fork_version(
        fork_data,
        current_slot,
    )


@pytest.mark.parametrize(
    (
        'pre_fork_version,'
        'post_fork_version,'
        'fork_slot,'
        'current_slot,'
        'domain_type,'
        'expected'
    ),
    [
        (1, 2, 20, 10, 10, 1 * 2 ** 32 + 10),
        (1, 2, 20, 20, 11, 2 * 2 ** 32 + 11),
        (1, 2, 10, 20, 12, 2 * 2 ** 32 + 12),
    ]
)
def test_get_domain(pre_fork_version,
                    post_fork_version,
                    fork_slot,
                    current_slot,
                    domain_type,
                    expected):
    fork_data = ForkData(
        pre_fork_version=pre_fork_version,
        post_fork_version=post_fork_version,
        fork_slot=fork_slot,
    )
    assert expected == get_domain(
        fork_data=fork_data,
        slot=current_slot,
        domain_type=domain_type,
    )


def _generate_some_indices(data, max_value_for_list):
    """
    Hypothesis helper that generates a list of some integers [0, `max_value_for_list`].
    The usage is to randomly sample some elements from a sequence of some element.
    """
    return data.draw(
        st.lists(
            st.integers(
                min_value=0,
                max_value=max_value_for_list,
            ),
        )
    )


@given(st.data())
def test_get_pubkey_for_indices(activated_genesis_validators, data):
    max_value_for_list = len(activated_genesis_validators) - 1
    indices = _generate_some_indices(data, max_value_for_list)
    pubkeys = get_pubkey_for_indices(activated_genesis_validators, indices)

    assert len(indices) == len(pubkeys)

    for index, pubkey in enumerate(pubkeys):
        validator_index = indices[index]
        assert activated_genesis_validators[validator_index].pubkey == pubkey


def _list_and_index(data, max_size=None, elements=st.integers()):
    '''
    Hypothesis helper function cribbed from their docs on @composite
    '''
    xs = data.draw(st.lists(elements, max_size=max_size))
    i = data.draw(st.integers(min_value=0, max_value=max(len(xs) - 1, 0)))
    return (xs, i)


@given(st.data())
def test_generate_aggregate_pubkeys(activated_genesis_validators,
                                    sample_slashable_vote_data_params,
                                    data):
    max_value_for_list = len(activated_genesis_validators) - 1
    (indices, some_index) = _list_and_index(
        data,
        elements=st.integers(
            min_value=0,
            max_value=max_value_for_list,
        )
    )
    custody_bit_0_indices = indices[:some_index]
    custody_bit_1_indices = indices[some_index:]

    key = "custody_bit_0_indices"
    sample_slashable_vote_data_params[key] = custody_bit_0_indices
    key = "custody_bit_1_indices"
    sample_slashable_vote_data_params[key] = custody_bit_1_indices

    votes = SlashableVoteData(**sample_slashable_vote_data_params)

    keys = generate_aggregate_pubkeys(activated_genesis_validators, votes)
    assert len(keys) == 2

    (poc_0_key, poc_1_key) = keys

    poc_0_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_0_indices)
    poc_1_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_1_indices)

    assert bls.aggregate_pubkeys(poc_0_keys) == poc_0_key
    assert bls.aggregate_pubkeys(poc_1_keys) == poc_1_key


@given(st.data())
def test_verify_vote_count(max_casper_votes, sample_slashable_vote_data_params, data):
    (indices, some_index) = _list_and_index(data, max_size=max_casper_votes)
    custody_bit_0_indices = indices[:some_index]
    custody_bit_1_indices = indices[some_index:]

    key = "custody_bit_0_indices"
    sample_slashable_vote_data_params[key] = custody_bit_0_indices
    key = "custody_bit_1_indices"
    sample_slashable_vote_data_params[key] = custody_bit_1_indices

    votes = SlashableVoteData(**sample_slashable_vote_data_params)

    assert verify_vote_count(votes, max_casper_votes)


def _get_indices_and_signatures(num_validators, message, privkeys, fork_data, slot):
    num_indices = 5
    assert num_validators >= num_indices
    indices = random.sample(range(num_validators), num_indices)
    privkeys = [privkeys[i] for i in indices]
    domain_type = SignatureDomain.DOMAIN_ATTESTATION
    domain = get_domain(
        fork_data=fork_data,
        slot=slot,
        domain_type=domain_type,
    )
    signatures = tuple(
        map(lambda key: bls.sign(message, key, domain), privkeys)
    )
    return (indices, signatures)


def _correct_slashable_vote_data_params(num_validators, params, messages, privkeys, fork_data):
    valid_params = copy.deepcopy(params)

    key = "custody_bit_0_indices"
    (poc_0_indices, poc_0_signatures) = _get_indices_and_signatures(
        num_validators,
        messages[0],
        privkeys,
        fork_data,
        params["data"].slot,
    )
    valid_params[key] = poc_0_indices

    key = "custody_bit_1_indices"
    # NOTE: does not guarantee non-empty intersection
    (poc_1_indices, poc_1_signatures) = _get_indices_and_signatures(
        num_validators,
        messages[1],
        privkeys,
        fork_data,
        params["data"].slot,
    )
    valid_params[key] = poc_1_indices

    signatures = poc_0_signatures + poc_1_signatures
    aggregate_signature = bls.aggregate_signatures(signatures)

    valid_params["aggregate_signature"] = aggregate_signature

    return valid_params


def _corrupt_signature(params, fork_data):
    message = bytes.fromhex("deadbeefcafe")
    privkey = 42
    domain_type = SignatureDomain.DOMAIN_ATTESTATION
    domain = get_domain(
        fork_data=fork_data,
        slot=params["data"].slot,
        domain_type=domain_type,
    )
    corrupt_signature = bls.sign(message, privkey, domain)

    return assoc(params, "aggregate_signature", corrupt_signature)


def _corrupt_vote_count(params):
    key = "custody_bit_0_indices"
    for i in itertools.count():
        if i not in params[key]:
            new_vote_count = params[key] + [i]
            return assoc(
                params,
                key,
                new_vote_count,
            )
    else:
        raise Exception("Unreachable code path")


def _create_slashable_vote_data_messages(params):
    # TODO update when we move to `ssz` tree hash
    votes = SlashableVoteData(**params)
    return votes.messages


@pytest.mark.parametrize(
    (
        'num_validators',
    ),
    [
        (40,),
    ]
)
def test_verify_slashable_vote_data_signature(num_validators,
                                              privkeys,
                                              sample_beacon_state_params,
                                              activated_genesis_validators,
                                              genesis_balances,
                                              sample_slashable_vote_data_params,
                                              sample_fork_data_params):
    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        fork_data=ForkData(**sample_fork_data_params),
    )

    # NOTE: we can do this before "correcting" the params as they
    # touch disjoint subsets of the provided params
    messages = _create_slashable_vote_data_messages(sample_slashable_vote_data_params)

    valid_params = _correct_slashable_vote_data_params(
        num_validators,
        sample_slashable_vote_data_params,
        messages,
        privkeys,
        state.fork_data,
    )
    valid_votes = SlashableVoteData(**valid_params)
    assert verify_slashable_vote_data_signature(state, valid_votes)

    invalid_params = _corrupt_signature(valid_params, state.fork_data)
    invalid_votes = SlashableVoteData(**invalid_params)
    assert not verify_slashable_vote_data_signature(state, invalid_votes)


def _run_verify_slashable_vote(params, state, max_casper_votes, should_succeed):
    votes = SlashableVoteData(**params)
    result = verify_slashable_vote_data(state, votes, max_casper_votes)
    if should_succeed:
        assert result
    else:
        assert not result


@pytest.mark.parametrize(
    (
        'num_validators',
    ),
    [
        (40,),
    ]
)
@pytest.mark.parametrize(
    (
        'param_mapper',
        'should_succeed',
        'needs_fork_data',
    ),
    [
        (lambda params: params, True, False),
        (_corrupt_vote_count, False, False),
        (_corrupt_signature, False, True),
        (lambda params, fork_data: _corrupt_vote_count(
            _corrupt_signature(params, fork_data)
        ), False, True),
    ],
)
def test_verify_slashable_vote_data(num_validators,
                                    param_mapper,
                                    should_succeed,
                                    needs_fork_data,
                                    privkeys,
                                    sample_beacon_state_params,
                                    activated_genesis_validators,
                                    genesis_balances,
                                    sample_slashable_vote_data_params,
                                    sample_fork_data_params,
                                    max_casper_votes):
    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        fork_data=ForkData(**sample_fork_data_params),
    )

    # NOTE: we can do this before "correcting" the params as they
    # touch disjoint subsets of the provided params
    messages = _create_slashable_vote_data_messages(sample_slashable_vote_data_params)

    params = _correct_slashable_vote_data_params(
        num_validators,
        sample_slashable_vote_data_params,
        messages,
        privkeys,
        state.fork_data,
    )
    if needs_fork_data:
        params = param_mapper(params, state.fork_data)
    else:
        params = param_mapper(params)
    _run_verify_slashable_vote(params, state, max_casper_votes, should_succeed)


def test_is_double_vote(sample_attestation_data_params):
    attestation_data_1_params = {
        **sample_attestation_data_params,
        'slot': 12345,
    }
    attestation_data_1 = AttestationData(**attestation_data_1_params)

    attestation_data_2_params = {
        **sample_attestation_data_params,
        'slot': 12345,
    }
    attestation_data_2 = AttestationData(**attestation_data_2_params)

    assert is_double_vote(attestation_data_1, attestation_data_2)

    attestation_data_3_params = {
        **sample_attestation_data_params,
        'slot': 54321,
    }
    attestation_data_3 = AttestationData(**attestation_data_3_params)

    assert not is_double_vote(attestation_data_1, attestation_data_3)


@pytest.mark.parametrize(
    (
        'attestation_1_slot,'
        'attestation_1_justified_slot,'
        'attestation_2_slot,'
        'attestation_2_justified_slot,'
        'expected'
    ),
    [
        (0, 0, 0, 0, False),
        (4, 3, 3, 2, False),  # not (attestation_1_justified_slot < attestation_2_justified_slot
        (4, 0, 3, 1, False),  # not (attestation_2_justified_slot + 1 == attestation_2_slot)
        (4, 0, 4, 3, False),  # not (attestation_2_slot < attestation_1_slot)
        (4, 0, 3, 2, True),
    ],
)
def test_is_surround_vote(sample_attestation_data_params,
                          attestation_1_slot,
                          attestation_1_justified_slot,
                          attestation_2_slot,
                          attestation_2_justified_slot,
                          expected):
    attestation_data_1_params = {
        **sample_attestation_data_params,
        'slot': attestation_1_slot,
        'justified_slot': attestation_1_justified_slot,
    }
    attestation_data_1 = AttestationData(**attestation_data_1_params)

    attestation_data_2_params = {
        **sample_attestation_data_params,
        'slot': attestation_2_slot,
        'justified_slot': attestation_2_justified_slot,
    }
    attestation_data_2 = AttestationData(**attestation_data_2_params)

    assert is_surround_vote(attestation_data_1, attestation_data_2) == expected
