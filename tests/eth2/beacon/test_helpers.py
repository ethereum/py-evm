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
from eth_utils.toolz import (
    assoc,
    isdistinct,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
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
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.slashable_attestations import SlashableAttestation
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validator_records import ValidatorRecord
from eth2.beacon.helpers import (
    _get_block_root,
    generate_seed,
    get_active_validator_indices,
    get_attestation_participants,
    get_beacon_proposer_index,
    get_committee_count_per_slot,
    get_crosslink_committees_at_slot,
    get_current_epoch_committee_count_per_slot,
    get_domain,
    get_effective_balance,
    get_entry_exit_effect_slot,
    get_fork_version,
    get_previous_epoch_committee_count_per_slot,
    get_pubkey_for_indices,
    get_shuffling,
    generate_aggregate_pubkeys,
    verify_vote_count,
    verify_slashable_attestation_signature,
    verify_slashable_attestation,
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
# Shuffling
#
@pytest.mark.parametrize(
    (
        'active_validator_count,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'expected_committee_count'
    ),
    [
        (1000, 20, 10, 50, 2),  # SHARD_COUNT // EPOCH_LENGTH
        (1000, 20, 10, 100, 5),  # active_validator_count // EPOCH_LENGTH // TARGET_COMMITTEE_SIZE
        (20, 10, 3, 10, 1),  # 1
        (20, 10, 3, 5, 1),  # 1
        (40, 5, 2, 2, 1),  # 1
    ],
)
def test_get_committee_count_per_slot(active_validator_count,
                                      epoch_length,
                                      target_committee_size,
                                      shard_count,
                                      expected_committee_count):
    assert expected_committee_count == get_committee_count_per_slot(
        active_validator_count=active_validator_count,
        shard_count=shard_count,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )


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
        slot=slot,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    assert len(shuffling) == epoch_length
    assert len(shuffling) > 0
    for committee in shuffling:
        assert len(committee) <= target_committee_size
        assert len(committee) > 0
    validator_indices = tuple(
        itertools.chain(
            [
                validator_index
                for committee in shuffling
                for validator_index in committee
            ]
        )
    )
    assert isdistinct(validator_indices)
    activated_genesis_validator_indices = tuple(
        index
        for index in range(len(activated_genesis_validators))
    )
    assert sorted(validator_indices) == sorted(activated_genesis_validator_indices)


@pytest.mark.parametrize(
    (
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'len_active_validators,'
        'previous_epoch_calculation_slot, current_epoch_calculation_slot,'
        'get_epoch_committee_count_per_slot,'
        'delayed_activation_slot'
    ),
    [
        (
            1, 1, 2, 2,
            5, 10,
            get_previous_epoch_committee_count_per_slot,
            5 + 1,
        ),
        (
            1, 1, 2, 10,
            5, 10,
            get_previous_epoch_committee_count_per_slot,
            5 + 1,
        ),
        (
            1, 1, 2, 2,
            5, 10,
            get_current_epoch_committee_count_per_slot,
            10 + 1,
        ),
        (
            1, 1, 2, 10,
            5, 10,
            get_current_epoch_committee_count_per_slot,
            10 + 1,
        ),
    ],
)
def test_get_epoch_committee_count_per_slot(monkeypatch,
                                            ten_validators_state,
                                            epoch_length,
                                            target_committee_size,
                                            shard_count,
                                            len_active_validators,
                                            previous_epoch_calculation_slot,
                                            current_epoch_calculation_slot,
                                            get_epoch_committee_count_per_slot,
                                            delayed_activation_slot):
    from eth2.beacon import helpers

    def mock_get_committee_count_per_slot(active_validator_count,
                                          shard_count,
                                          epoch_length,
                                          target_committee_size):
        return active_validator_count // epoch_length // shard_count

    monkeypatch.setattr(
        helpers,
        'get_committee_count_per_slot',
        mock_get_committee_count_per_slot
    )

    state = ten_validators_state.copy(
        slot=0,
        previous_epoch_calculation_slot=previous_epoch_calculation_slot,
        current_epoch_calculation_slot=current_epoch_calculation_slot,
    )
    for index in range(len(state.validator_registry)):
        if index < len_active_validators:
            validator = state.validator_registry[index].copy(
                activation_slot=0,
            )
            state = state.update_validator_registry(
                index,
                validator,
            )
        else:
            validator = state.validator_registry[index].copy(
                activation_slot=delayed_activation_slot,
            )
            state = state.update_validator_registry(
                index,
                validator,
            )

    result_committee_count = get_epoch_committee_count_per_slot(
        state=state,
        shard_count=shard_count,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )
    expected_committee_count = len_active_validators // epoch_length // shard_count

    assert result_committee_count == expected_committee_count


@pytest.mark.parametrize(
    (
        'state_epoch_slot,'
        'slot,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
    ),
    [
        (10, 5, 10, 10, 10),  # slot < state_epoch_slot
        (10, 10, 10, 10, 10),  # slot >= state_epoch_slot
        (10, 11, 10, 10, 10),  # slot >= state_epoch_slot
    ],
)
def test_get_crosslink_committees_at_slot(
        ten_validators_state,
        state_epoch_slot,
        slot,
        epoch_length,
        target_committee_size,
        shard_count):

    state = ten_validators_state.copy(
        slot=state_epoch_slot,
    )

    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state=state,
        slot=slot,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    assert len(crosslink_committees_at_slot) > 0
    for crosslink_committee in crosslink_committees_at_slot:
        committee, shard = crosslink_committee
        assert len(committee) > 0
        assert shard < shard_count


#
# Get proposer postition
#
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
        sample_state,
        target_committee_size,
        shard_count):

    from eth2.beacon import helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              epoch_length,
                                              target_committee_size,
                                              shard_count):
        return (
            (committee, 1,),
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
            epoch_length,
            target_committee_size,
            shard_count,
        )
        assert proposer_index == committee[slot % len(committee)]
    else:
        with pytest.raises(ValidationError):
            get_beacon_proposer_index(
                sample_state,
                slot,
                epoch_length,
                target_committee_size,
                shard_count,
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
        'aggregation_bitfield,'
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
        aggregation_bitfield,
        expected,
        sample_state,
        target_committee_size,
        shard_count,
        sample_attestation_data_params):
    shard = 1

    from eth2.beacon import helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              epoch_length,
                                              target_committee_size,
                                              shard_count):
        return (
            (committee, shard,),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=0,
        shard=shard,
    )
    if isinstance(expected, Exception):
        with pytest.raises(ValidationError):
            get_attestation_participants(
                state=sample_state,
                attestation_data=attestation_data,
                aggregation_bitfield=aggregation_bitfield,
                epoch_length=epoch_length,
                target_committee_size=target_committee_size,
                shard_count=shard_count,
            )
    else:
        result = get_attestation_participants(
            state=sample_state,
            attestation_data=attestation_data,
            aggregation_bitfield=aggregation_bitfield,
            epoch_length=epoch_length,
            target_committee_size=target_committee_size,
            shard_count=shard_count,
        )

        assert result == expected


@pytest.mark.parametrize(
    (
        'balance,'
        'max_deposit_amount,'
        'expected'
    ),
    [
        (
            1 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
            1 * GWEI_PER_ETH,
        ),
        (
            32 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
        ),
        (
            33 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
        )
    ]
)
def test_get_effective_balance(balance,
                               max_deposit_amount,
                               expected,
                               sample_validator_record_params):
    balances = (balance,)
    result = get_effective_balance(balances, 0, max_deposit_amount)
    assert result == expected


@pytest.mark.parametrize(
    (
        'previous_version,'
        'current_version,'
        'slot,'
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
def test_get_fork_version(previous_version,
                          current_version,
                          slot,
                          current_slot,
                          expected):
    fork = Fork(
        previous_version=previous_version,
        current_version=current_version,
        slot=slot,
    )
    assert expected == get_fork_version(
        fork,
        current_slot,
    )


@pytest.mark.parametrize(
    (
        'previous_version,'
        'current_version,'
        'slot,'
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
def test_get_domain(previous_version,
                    current_version,
                    slot,
                    current_slot,
                    domain_type,
                    expected):
    fork = Fork(
        previous_version=previous_version,
        current_version=current_version,
        slot=slot,
    )
    assert expected == get_domain(
        fork=fork,
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
    """
    Hypothesis helper function cribbed from their docs on @composite
    """
    xs = data.draw(st.lists(elements, max_size=max_size))
    i = data.draw(st.integers(min_value=0, max_value=max(len(xs) - 1, 0)))
    return (xs, i)


@given(st.data())
def test_generate_aggregate_pubkeys(activated_genesis_validators,
                                    sample_slashable_attestation_params,
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
    sample_slashable_attestation_params[key] = custody_bit_0_indices
    key = "custody_bit_1_indices"
    sample_slashable_attestation_params[key] = custody_bit_1_indices

    votes = SlashableAttestation(**sample_slashable_attestation_params)

    keys = generate_aggregate_pubkeys(activated_genesis_validators, votes)
    assert len(keys) == 2

    (poc_0_key, poc_1_key) = keys

    poc_0_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_0_indices)
    poc_1_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_1_indices)

    assert bls.aggregate_pubkeys(poc_0_keys) == poc_0_key
    assert bls.aggregate_pubkeys(poc_1_keys) == poc_1_key


@given(st.data())
def test_verify_vote_count(max_indices_per_slashable_vote,
                           sample_slashable_attestation_params,
                           data):
    (indices, some_index) = _list_and_index(data, max_size=max_indices_per_slashable_vote)
    custody_bit_0_indices = indices[:some_index]
    custody_bit_1_indices = indices[some_index:]

    key = "custody_bit_0_indices"
    sample_slashable_attestation_params[key] = custody_bit_0_indices
    key = "custody_bit_1_indices"
    sample_slashable_attestation_params[key] = custody_bit_1_indices

    votes = SlashableAttestation(**sample_slashable_attestation_params)

    assert verify_vote_count(votes, max_indices_per_slashable_vote)


def _get_indices_and_signatures(num_validators, message, privkeys, fork, slot):
    num_indices = 5
    assert num_validators >= num_indices
    indices = random.sample(range(num_validators), num_indices)
    privkeys = [privkeys[i] for i in indices]
    domain_type = SignatureDomain.DOMAIN_ATTESTATION
    domain = get_domain(
        fork=fork,
        slot=slot,
        domain_type=domain_type,
    )
    signatures = tuple(
        map(lambda key: bls.sign(message, key, domain), privkeys)
    )
    return (indices, signatures)


def _correct_slashable_attestation_params(num_validators, params, messages, privkeys, fork):
    valid_params = copy.deepcopy(params)

    key = "custody_bit_0_indices"
    (poc_0_indices, poc_0_signatures) = _get_indices_and_signatures(
        num_validators,
        messages[0],
        privkeys,
        fork,
        params["data"].slot,
    )
    valid_params[key] = poc_0_indices

    key = "custody_bit_1_indices"
    # NOTE: does not guarantee non-empty intersection
    (poc_1_indices, poc_1_signatures) = _get_indices_and_signatures(
        num_validators,
        messages[1],
        privkeys,
        fork,
        params["data"].slot,
    )
    valid_params[key] = poc_1_indices

    signatures = poc_0_signatures + poc_1_signatures
    aggregate_signature = bls.aggregate_signatures(signatures)

    valid_params["aggregate_signature"] = aggregate_signature

    return valid_params


def _corrupt_signature(params, fork):
    message = bytes.fromhex("deadbeefcafe")
    privkey = 42
    domain_type = SignatureDomain.DOMAIN_ATTESTATION
    domain = get_domain(
        fork=fork,
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


def _create_slashable_attestation_messages(params):
    # TODO update when we move to `ssz` tree hash
    votes = SlashableAttestation(**params)
    return votes.messages


@pytest.mark.parametrize(
    (
        'num_validators',
    ),
    [
        (40,),
    ]
)
def test_verify_slashable_attestation_signature(
        num_validators,
        privkeys,
        sample_beacon_state_params,
        activated_genesis_validators,
        genesis_balances,
        sample_slashable_attestation_params,
        sample_fork_params):
    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        fork=Fork(**sample_fork_params),
    )

    # NOTE: we can do this before "correcting" the params as they
    # touch disjoint subsets of the provided params
    messages = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    valid_params = _correct_slashable_attestation_params(
        num_validators,
        sample_slashable_attestation_params,
        messages,
        privkeys,
        state.fork,
    )
    valid_votes = SlashableAttestation(**valid_params)
    assert verify_slashable_attestation_signature(state, valid_votes)

    invalid_params = _corrupt_signature(valid_params, state.fork)
    invalid_votes = SlashableAttestation(**invalid_params)
    assert not verify_slashable_attestation_signature(state, invalid_votes)


def _run_verify_slashable_vote(params, state, max_indices_per_slashable_vote, should_succeed):
    votes = SlashableAttestation(**params)
    result = verify_slashable_attestation(state, votes, max_indices_per_slashable_vote)
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
        'needs_fork',
    ),
    [
        (lambda params: params, True, False),
        (_corrupt_vote_count, False, False),
        (_corrupt_signature, False, True),
        (lambda params, fork: _corrupt_vote_count(
            _corrupt_signature(params, fork)
        ), False, True),
    ],
)
def test_verify_slashable_attestation(
        num_validators,
        param_mapper,
        should_succeed,
        needs_fork,
        privkeys,
        sample_beacon_state_params,
        activated_genesis_validators,
        genesis_balances,
        sample_slashable_attestation_params,
        sample_fork_params,
        max_indices_per_slashable_vote):
    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        fork=Fork(**sample_fork_params),
    )

    # NOTE: we can do this before "correcting" the params as they
    # touch disjoint subsets of the provided params
    messages = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    params = _correct_slashable_attestation_params(
        num_validators,
        sample_slashable_attestation_params,
        messages,
        privkeys,
        state.fork,
    )
    if needs_fork:
        params = param_mapper(params, state.fork)
    else:
        params = param_mapper(params)
    _run_verify_slashable_vote(params, state, max_indices_per_slashable_vote, should_succeed)


@pytest.mark.parametrize(
    (
        'num_validators',
    ),
    [
        (40,),
    ]
)
def test_verify_slashable_attestation_after_fork(
        num_validators,
        privkeys,
        sample_beacon_state_params,
        activated_genesis_validators,
        genesis_balances,
        sample_slashable_attestation_params,
        sample_fork_params,
        max_indices_per_slashable_vote):
    # Test that slashable data is still valid after fork
    # Slashable data slot = 10, fork slot = 15, current slot = 20
    past_fork_params = {
        'previous_version': 0,
        'current_version': 1,
        'slot': 15,
    }

    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        fork=Fork(**past_fork_params),
        slot=20,
    )

    messages = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    valid_params = _correct_slashable_attestation_params(
        num_validators,
        sample_slashable_attestation_params,
        messages,
        privkeys,
        state.fork,
    )
    _run_verify_slashable_vote(valid_params, state, max_indices_per_slashable_vote, True)


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


@pytest.mark.parametrize(
    (
        'slot,'
        'epoch_length,'
        'entry_exit_delay,'
        'expected_entry_exit_effect_slot'
    ),
    # result = (slot - slot % EPOCH_LENGTH) + EPOCH_LENGTH + ENTRY_EXIT_DELAY
    [
        (64, 64, 128, (64 - 64 % 64) + 64 + 128),
        (128, 64, 128, (128 - 128 % 64) + 64 + 128),
    ],
)
def test_get_entry_exit_effect_slot(slot,
                                    epoch_length,
                                    entry_exit_delay,
                                    expected_entry_exit_effect_slot):
    # TODO: update to epoch version
    entry_exit_effect_slot = get_entry_exit_effect_slot(
        slot,
        epoch_length,
        entry_exit_delay,
    )
    assert entry_exit_effect_slot == expected_entry_exit_effect_slot


def test_generate_seed(monkeypatch,
                       genesis_state,
                       epoch_length,
                       seed_lookahead,
                       latest_index_roots_length,
                       latest_randao_mixes_length):
    from eth2.beacon import helpers

    def mock_get_randao_mix(state,
                            slot,
                            latest_randao_mixes_length):
        return hash_eth2(
            state.root +
            abs(slot).to_bytes(32, byteorder='big') +
            latest_randao_mixes_length.to_bytes(32, byteorder='big')
        )

    def mock_get_active_index_root(state,
                                   slot,
                                   epoch_length,
                                   latest_index_roots_length):
        return hash_eth2(
            state.root +
            abs(slot).to_bytes(32, byteorder='big') +
            epoch_length.to_bytes(32, byteorder='big') +
            latest_index_roots_length.to_bytes(32, byteorder='big')
        )

    monkeypatch.setattr(
        helpers,
        'get_randao_mix',
        mock_get_randao_mix
    )
    monkeypatch.setattr(
        helpers,
        'get_active_index_root',
        mock_get_active_index_root
    )

    state = genesis_state
    slot = 10

    seed = generate_seed(
        state=state,
        slot=slot,
        epoch_length=epoch_length,
        seed_lookahead=seed_lookahead,
        latest_index_roots_length=latest_index_roots_length,
        latest_randao_mixes_length=latest_randao_mixes_length,
    )
    assert seed == hash_eth2(
        mock_get_randao_mix(
            state,
            slot - seed_lookahead,
            latest_randao_mixes_length=latest_randao_mixes_length,
        ) + mock_get_active_index_root(
            state,
            slot,
            epoch_length=epoch_length,
            latest_index_roots_length=latest_index_roots_length,
        )
    )
