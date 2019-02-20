import copy
import random

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
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2._utils.bitfield import (
    get_empty_bitfield,
    set_voted,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.constants import (
    GWEI_PER_ETH,
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.enums import (
    SignatureDomain,
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
    generate_aggregate_pubkeys,
    generate_seed,
    get_active_validator_indices,
    get_domain,
    get_effective_balance,
    get_entry_exit_effect_epoch,
    get_fork_version,
    get_pubkey_for_indices,
    get_total_balance,
    is_double_vote,
    is_surround_vote,
    slot_to_epoch,
    validate_slashable_attestation,
    verify_slashable_attestation_signature,
)
import eth2._utils.bls as bls

from tests.eth2.beacon.helpers import (
    get_pseudo_chain,
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


def test_get_active_validator_indices(sample_validator_record_params):
    current_epoch = 1
    # 3 validators are ACTIVE
    validators = [
        ValidatorRecord(
            **sample_validator_record_params,
        ).copy(
            activation_epoch=0,
            exit_epoch=FAR_FUTURE_EPOCH,
        )
        for i in range(3)
    ]
    active_validator_indices = get_active_validator_indices(validators, current_epoch)
    assert len(active_validator_indices) == 3

    validators[0] = validators[0].copy(
        activation_epoch=current_epoch + 1,  # activation_epoch > current_epoch
    )
    active_validator_indices = get_active_validator_indices(validators, current_epoch)
    assert len(active_validator_indices) == 2

    validators[1] = validators[1].copy(
        exit_epoch=current_epoch,  # current_epoch == exit_epoch
    )
    active_validator_indices = get_active_validator_indices(validators, current_epoch)
    assert len(active_validator_indices) == 1


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
        'validator_balances,'
        'validator_indices,'
        'max_deposit_amount,'
        'expected'
    ),
    [
        (
            tuple(),
            tuple(),
            1 * GWEI_PER_ETH,
            0,
        ),
        (
            (32 * GWEI_PER_ETH, 32 * GWEI_PER_ETH),
            (0, 1),
            32 * GWEI_PER_ETH,
            64 * GWEI_PER_ETH,
        ),
        (
            (32 * GWEI_PER_ETH, 32 * GWEI_PER_ETH),
            (1,),
            32 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
        ),
        (
            (32 * GWEI_PER_ETH, 32 * GWEI_PER_ETH),
            (0, 1),
            16 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
        ),
    ]
)
def test_get_total_balance(validator_balances,
                           validator_indices,
                           max_deposit_amount,
                           expected):
    total_balance = get_total_balance(validator_balances, validator_indices, max_deposit_amount)
    assert total_balance == expected


@pytest.mark.parametrize(
    (
        'previous_version,'
        'current_version,'
        'epoch,'
        'current_epoch,'
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
                          epoch,
                          current_epoch,
                          expected):
    fork = Fork(
        previous_version=previous_version,
        current_version=current_version,
        epoch=epoch,
    )
    assert expected == get_fork_version(
        fork,
        current_epoch,
    )


@pytest.mark.parametrize(
    (
        'previous_version,'
        'current_version,'
        'epoch,'
        'current_epoch,'
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
                    epoch,
                    current_epoch,
                    domain_type,
                    expected):
    fork = Fork(
        previous_version=previous_version,
        current_version=current_version,
        epoch=epoch,
    )
    assert expected == get_domain(
        fork=fork,
        epoch=current_epoch,
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
    xs = data.draw(st.lists(elements, max_size=max_size, unique=True))
    i = data.draw(st.integers(min_value=0, max_value=max(len(xs) - 1, 0)))
    return (xs, i)


@given(st.data())
def test_generate_aggregate_pubkeys(activated_genesis_validators,
                                    sample_slashable_attestation_params,
                                    data):
    max_value_for_list = len(activated_genesis_validators) - 1
    (validator_indices, some_index) = _list_and_index(
        data,
        elements=st.integers(
            min_value=0,
            max_value=max_value_for_list,
        )
    )

    key = "validator_indices"
    sample_slashable_attestation_params[key] = validator_indices

    custody_bitfield = get_empty_bitfield(len(validator_indices))
    for index in range(some_index):
        custody_bitfield = set_voted(custody_bitfield, index)

    key = "custody_bitfield"
    sample_slashable_attestation_params[key] = custody_bitfield

    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params)
    custody_bit_0_indices, custody_bit_1_indices = slashable_attestation.custody_bit_indices
    assert len(
        set(custody_bit_0_indices).intersection(set(custody_bit_1_indices))
    ) == 0

    keys = generate_aggregate_pubkeys(activated_genesis_validators, slashable_attestation)
    assert len(keys) == 2

    (poc_0_key, poc_1_key) = keys

    poc_0_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_0_indices)
    poc_1_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_1_indices)

    assert bls.aggregate_pubkeys(poc_0_keys) == poc_0_key
    assert bls.aggregate_pubkeys(poc_1_keys) == poc_1_key


def _get_indices_and_signatures(num_validators, message, privkeys, fork, epoch):
    num_indices = 5
    assert num_validators >= num_indices
    indices = random.sample(range(num_validators), num_indices)
    indices.sort()

    privkeys = [privkeys[i] for i in indices]
    domain_type = SignatureDomain.DOMAIN_ATTESTATION
    domain = get_domain(
        fork=fork,
        epoch=epoch,
        domain_type=domain_type,
    )
    signatures = tuple(
        map(lambda key: bls.sign(message, key, domain), privkeys)
    )
    return (indices, signatures)


def _correct_slashable_attestation_params(
        epoch_length,
        num_validators,
        params,
        messages,
        privkeys,
        fork):
    valid_params = copy.deepcopy(params)

    (validator_indices, signatures) = _get_indices_and_signatures(
        num_validators,
        messages[1],
        privkeys,
        fork,
        slot_to_epoch(params["data"].slot, epoch_length),
    )

    valid_params["validator_indices"] = validator_indices
    valid_params["custody_bitfield"] = get_empty_bitfield(len(validator_indices))

    aggregate_signature = bls.aggregate_signatures(signatures)

    valid_params["aggregate_signature"] = aggregate_signature

    return valid_params


def _corrupt_custody_bitfield_not_empty(params):
    validator_indices_length = len(params["validator_indices"])
    corrupt_custody_bitfield = get_empty_bitfield(validator_indices_length)
    corrupt_custody_bitfield = set_voted(corrupt_custody_bitfield, 0)
    return assoc(params, "custody_bitfield", corrupt_custody_bitfield)


def _corrupt_validator_indices(params):
    corrupt_validator_indices = (
        params["validator_indices"][1],
        params["validator_indices"][0],
    ) + tuple(params["validator_indices"][2:])

    return assoc(params, "validator_indices", corrupt_validator_indices)


def _corrupt_custody_bitfield_invalid(params):
    validator_indices_length = len(params["validator_indices"])
    corrupt_custody_bitfield = get_empty_bitfield(validator_indices_length + 8)
    return assoc(params, "custody_bitfield", corrupt_custody_bitfield)


def _corrupt_validator_indices_max(max_indices_per_slashable_vote, params):
    corrupt_validator_indices = [
        i
        for i in range(max_indices_per_slashable_vote + 1)
    ]
    return assoc(params, "validator_indices", corrupt_validator_indices)


def _corrupt_signature(epoch_length, params, fork):
    message = bytes.fromhex("deadbeefcafe")
    privkey = 42
    domain_type = SignatureDomain.DOMAIN_ATTESTATION
    domain = get_domain(
        fork=fork,
        epoch=slot_to_epoch(params["data"].slot, epoch_length),
        domain_type=domain_type,
    )
    corrupt_signature = bls.sign(message, privkey, domain)

    return assoc(params, "aggregate_signature", corrupt_signature)


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
        epoch_length,
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
        epoch_length,
        num_validators,
        sample_slashable_attestation_params,
        messages,
        privkeys,
        state.fork,
    )
    valid_votes = SlashableAttestation(**valid_params)
    assert verify_slashable_attestation_signature(state, valid_votes, epoch_length)

    invalid_params = _corrupt_signature(epoch_length, valid_params, state.fork)
    invalid_votes = SlashableAttestation(**invalid_params)
    assert not verify_slashable_attestation_signature(state, invalid_votes, epoch_length)


def _run_verify_slashable_vote(
        epoch_length,
        params,
        state,
        max_indices_per_slashable_vote,
        should_succeed):
    votes = SlashableAttestation(**params)
    if should_succeed:
        validate_slashable_attestation(state, votes, max_indices_per_slashable_vote, epoch_length)
    else:
        with pytest.raises(ValidationError):
            validate_slashable_attestation(
                state,
                votes,
                max_indices_per_slashable_vote,
                epoch_length,
            )


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
        'is_testing_max_length',
    ),
    [
        (lambda params: params, True, False, False),
        (_corrupt_custody_bitfield_not_empty, False, False, False),
        (_corrupt_validator_indices, False, False, False),
        (_corrupt_custody_bitfield_invalid, False, False, False),
        (_corrupt_validator_indices_max, False, False, True),
        (_corrupt_signature, False, True, False),
    ],
)
def test_validate_slashable_attestation(
        epoch_length,
        num_validators,
        param_mapper,
        should_succeed,
        needs_fork,
        is_testing_max_length,
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
        epoch_length,
        num_validators,
        sample_slashable_attestation_params,
        messages,
        privkeys,
        state.fork,
    )
    if needs_fork:
        params = param_mapper(epoch_length, params, state.fork)
    elif is_testing_max_length:
        params = param_mapper(max_indices_per_slashable_vote, params)

    else:
        params = param_mapper(params)
    _run_verify_slashable_vote(
        epoch_length,
        params,
        state,
        max_indices_per_slashable_vote,
        should_succeed,
    )


@pytest.mark.parametrize(
    (
        'num_validators',
    ),
    [
        (40,),
    ]
)
def test_verify_slashable_attestation_after_fork(
        epoch_length,
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
        'epoch': 15,
    }

    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        fork=Fork(**past_fork_params),
        slot=20,
    )

    messages = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    valid_params = _correct_slashable_attestation_params(
        epoch_length,
        num_validators,
        sample_slashable_attestation_params,
        messages,
        privkeys,
        state.fork,
    )
    _run_verify_slashable_vote(
        epoch_length,
        valid_params,
        state,
        max_indices_per_slashable_vote,
        True,
    )


def test_is_double_vote(sample_attestation_data_params, epoch_length):
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

    assert is_double_vote(attestation_data_1, attestation_data_2, epoch_length)

    attestation_data_3_params = {
        **sample_attestation_data_params,
        'slot': 54321,
    }
    attestation_data_3 = AttestationData(**attestation_data_3_params)

    assert not is_double_vote(attestation_data_1, attestation_data_3, epoch_length)


@pytest.mark.parametrize(
    (
        'epoch_length,'
        'attestation_1_slot,'
        'attestation_1_justified_epoch,'
        'attestation_2_slot,'
        'attestation_2_justified_epoch,'
        'expected'
    ),
    [
        (1, 0, 0, 0, 0, False),
        # not (attestation_1_justified_epoch < attestation_2_justified_epoch
        (1, 4, 3, 3, 2, False),
        # not (slot_to_epoch(attestation_2_slot) < slot_to_epoch(attestation_1_slot))
        (1, 4, 0, 4, 3, False),
        (1, 4, 0, 3, 2, True),
    ],
)
def test_is_surround_vote(sample_attestation_data_params,
                          epoch_length,
                          attestation_1_slot,
                          attestation_1_justified_epoch,
                          attestation_2_slot,
                          attestation_2_justified_epoch,
                          expected):
    attestation_data_1_params = {
        **sample_attestation_data_params,
        'slot': attestation_1_slot,
        'justified_epoch': attestation_1_justified_epoch,
    }
    attestation_data_1 = AttestationData(**attestation_data_1_params)

    attestation_data_2_params = {
        **sample_attestation_data_params,
        'slot': attestation_2_slot,
        'justified_epoch': attestation_2_justified_epoch,
    }
    attestation_data_2 = AttestationData(**attestation_data_2_params)

    assert is_surround_vote(attestation_data_1, attestation_data_2, epoch_length) == expected


def test_get_entry_exit_effect_epoch(entry_exit_delay):
    epoch = random.randint(0, FAR_FUTURE_EPOCH)
    entry_exit_effect_epoch = get_entry_exit_effect_epoch(
        epoch,
        entry_exit_delay,
    )
    assert entry_exit_effect_epoch == (epoch + 1 + entry_exit_delay)


def test_generate_seed(monkeypatch,
                       genesis_state,
                       epoch_length,
                       seed_lookahead,
                       entry_exit_delay,
                       latest_index_roots_length,
                       latest_randao_mixes_length):
    from eth2.beacon import helpers

    def mock_get_randao_mix(state,
                            epoch,
                            epoch_length,
                            latest_randao_mixes_length):
        return hash_eth2(
            state.root +
            epoch.to_bytes(32, byteorder='little') +
            latest_randao_mixes_length.to_bytes(32, byteorder='little')
        )

    def mock_get_active_index_root(state,
                                   epoch,
                                   epoch_length,
                                   entry_exit_delay,
                                   latest_index_roots_length):
        return hash_eth2(
            state.root +
            epoch.to_bytes(32, byteorder='little') +
            epoch_length.to_bytes(32, byteorder='little') +
            latest_index_roots_length.to_bytes(32, byteorder='little')
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
    epoch = 1

    epoch_as_bytes = epoch.to_bytes(32, 'little')

    seed = generate_seed(
        state=state,
        epoch=epoch,
        epoch_length=epoch_length,
        seed_lookahead=seed_lookahead,
        entry_exit_delay=entry_exit_delay,
        latest_index_roots_length=latest_index_roots_length,
        latest_randao_mixes_length=latest_randao_mixes_length,
    )
    assert seed == hash_eth2(
        mock_get_randao_mix(
            state=state,
            epoch=(epoch - seed_lookahead),
            epoch_length=epoch_length,
            latest_randao_mixes_length=latest_randao_mixes_length,
        ) + mock_get_active_index_root(
            state=state,
            epoch=epoch,
            epoch_length=epoch_length,
            entry_exit_delay=entry_exit_delay,
            latest_index_roots_length=latest_index_roots_length,
        ) + epoch_as_bytes
    )
