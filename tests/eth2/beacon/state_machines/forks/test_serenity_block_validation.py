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

from eth2._utils import bls
from eth2._utils.bitfield import (
    get_empty_bitfield,
    set_voted,
)
from eth2.beacon.configs import (
    CommitteeConfig,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.helpers import (
    get_domain,
    slot_to_epoch,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    generate_aggregate_pubkeys_from_indices,
    get_pubkey_for_indices,
    validate_block_slot,
    validate_proposer_signature,
    validate_randao_reveal,
    validate_slashable_attestation,
    verify_slashable_attestation_signature,
)
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.proposal import (
    Proposal,
)
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.slashable_attestations import SlashableAttestation
from eth2.beacon.types.states import BeaconState

from tests.eth2.beacon.helpers import mock_validator_record


@pytest.mark.parametrize(
    'state_slot,'
    'block_slot,'
    'expected',
    (
        (10, 10, None),
        (1, 10, ValidationError()),
        (10, 1, ValidationError()),
    ),
)
def test_validate_block_slot(sample_beacon_state_params,
                             sample_beacon_block_params,
                             state_slot,
                             block_slot,
                             expected):
    state = BeaconState(**sample_beacon_state_params).copy(
        slot=state_slot,
    )
    block = BeaconBlock(**sample_beacon_block_params).copy(
        slot=block_slot,
    )
    if isinstance(expected, Exception):
        with pytest.raises(ValidationError):
            validate_block_slot(state, block)
    else:
        validate_block_slot(state, block)


@pytest.mark.parametrize(
    'slots_per_epoch, shard_count,'
    'proposer_privkey, proposer_pubkey, is_valid_signature',
    (
        (5, 2, 0, bls.privtopub(0), True, ),
        (5, 2, 0, bls.privtopub(0)[1:] + b'\x01', False),
        (5, 2, 0, b'\x01\x23', False),
        (5, 2, 123, bls.privtopub(123), True),
        (5, 2, 123, bls.privtopub(123)[1:] + b'\x01', False),
        (5, 2, 123, b'\x01\x23', False),
    )
)
def test_validate_proposer_signature(
        slots_per_epoch,
        shard_count,
        proposer_privkey,
        proposer_pubkey,
        is_valid_signature,
        sample_beacon_block_params,
        sample_beacon_state_params,
        beacon_chain_shard_number,
        genesis_epoch,
        target_committee_size,
        max_deposit_amount,
        config):

    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=tuple(
            mock_validator_record(proposer_pubkey, config)
            for _ in range(10)
        ),
        validator_balances=(max_deposit_amount,) * 10,
    )

    default_block = BeaconBlock(**sample_beacon_block_params)
    empty_signature_block_root = default_block.block_without_signature_root

    proposal_signed_root = Proposal(
        state.slot,
        beacon_chain_shard_number,
        empty_signature_block_root,
    ).signed_root

    proposed_block = BeaconBlock(**sample_beacon_block_params).copy(
        signature=bls.sign(
            message_hash=proposal_signed_root,
            privkey=proposer_privkey,
            domain=SignatureDomain.DOMAIN_PROPOSAL,
        ),
    )

    if is_valid_signature:
        validate_proposer_signature(
            state,
            proposed_block,
            beacon_chain_shard_number,
            CommitteeConfig(config),
        )
    else:
        with pytest.raises(ValidationError):
            validate_proposer_signature(
                state,
                proposed_block,
                beacon_chain_shard_number,
                CommitteeConfig(config),
            )


@pytest.mark.parametrize(
    ["is_valid", "epoch", "expected_epoch", "proposer_key_index", "expected_proposer_key_index"],
    (
        (True, 0, 0, 0, 0),
        (True, 1, 1, 1, 1),
        (False, 0, 1, 0, 0),
        (False, 0, 0, 0, 1),
    )
)
def test_randao_reveal_validation(is_valid,
                                  epoch,
                                  expected_epoch,
                                  proposer_key_index,
                                  expected_proposer_key_index,
                                  privkeys,
                                  pubkeys,
                                  sample_fork_params,
                                  config):
    message_hash = epoch.to_bytes(32, byteorder="little")
    slot = epoch * config.SLOTS_PER_EPOCH
    fork = Fork(**sample_fork_params)
    domain = get_domain(fork, slot, SignatureDomain.DOMAIN_RANDAO)

    proposer_privkey = privkeys[proposer_key_index]
    randao_reveal = bls.sign(
        message_hash=message_hash,
        privkey=proposer_privkey,
        domain=domain,
    )

    expected_proposer_pubkey = pubkeys[expected_proposer_key_index]

    try:
        validate_randao_reveal(
            randao_reveal=randao_reveal,
            proposer_index=expected_proposer_key_index,
            proposer_pubkey=expected_proposer_pubkey,
            epoch=expected_epoch,
            fork=fork,
        )
    except ValidationError:
        if is_valid:
            raise
    else:
        if not is_valid:
            pytest.fail("Did not raise")


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


def _list_and_index(data, max_size=None, elements=None):
    """
    Hypothesis helper function cribbed from their docs on @composite
    """
    if elements is None:
        elements = st.integers()
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

    keys = generate_aggregate_pubkeys_from_indices(
        activated_genesis_validators,
        *slashable_attestation.custody_bit_indices,
    )
    assert len(keys) == 2

    (poc_0_key, poc_1_key) = keys

    poc_0_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_0_indices)
    poc_1_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_1_indices)

    assert bls.aggregate_pubkeys(poc_0_keys) == poc_0_key
    assert bls.aggregate_pubkeys(poc_1_keys) == poc_1_key


def _get_indices_and_signatures(num_validators, message_hash, privkeys, fork, epoch):
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
        map(lambda key: bls.sign(message_hash, key, domain), privkeys)
    )
    return (indices, signatures)


def _correct_slashable_attestation_params(
        slots_per_epoch,
        num_validators,
        params,
        message_hashes,
        privkeys,
        fork):
    valid_params = copy.deepcopy(params)

    (validator_indices, signatures) = _get_indices_and_signatures(
        num_validators,
        message_hashes[0],  # custody bit is False
        privkeys,
        fork,
        slot_to_epoch(params["data"].slot, slots_per_epoch),
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


def _corrupt_signature(slots_per_epoch, params, fork):
    message_hash = b'\x12' * 32
    privkey = 42
    domain_type = SignatureDomain.DOMAIN_ATTESTATION
    domain = get_domain(
        fork=fork,
        epoch=slot_to_epoch(params["data"].slot, slots_per_epoch),
        domain_type=domain_type,
    )
    corrupt_signature = bls.sign(message_hash, privkey, domain)

    return assoc(params, "aggregate_signature", corrupt_signature)


def _create_slashable_attestation_messages(params):
    # TODO update when we move to `ssz` tree hash
    votes = SlashableAttestation(**params)
    return votes.message_hashes


@pytest.mark.parametrize(
    (
        'num_validators',
    ),
    [
        (40,),
    ]
)
def test_verify_slashable_attestation_signature(
        slots_per_epoch,
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
    message_hashes = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    valid_params = _correct_slashable_attestation_params(
        slots_per_epoch,
        num_validators,
        sample_slashable_attestation_params,
        message_hashes,
        privkeys,
        state.fork,
    )
    valid_votes = SlashableAttestation(**valid_params)
    assert verify_slashable_attestation_signature(state, valid_votes, slots_per_epoch)

    invalid_params = _corrupt_signature(slots_per_epoch, valid_params, state.fork)
    invalid_votes = SlashableAttestation(**invalid_params)
    assert not verify_slashable_attestation_signature(state, invalid_votes, slots_per_epoch)


def _run_verify_slashable_vote(
        slots_per_epoch,
        params,
        state,
        max_indices_per_slashable_vote,
        should_succeed):
    votes = SlashableAttestation(**params)
    if should_succeed:
        validate_slashable_attestation(
            state,
            votes,
            max_indices_per_slashable_vote,
            slots_per_epoch,
        )
    else:
        with pytest.raises(ValidationError):
            validate_slashable_attestation(
                state,
                votes,
                max_indices_per_slashable_vote,
                slots_per_epoch,
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
        slots_per_epoch,
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
    message_hashes = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    params = _correct_slashable_attestation_params(
        slots_per_epoch,
        num_validators,
        sample_slashable_attestation_params,
        message_hashes,
        privkeys,
        state.fork,
    )
    if needs_fork:
        params = param_mapper(slots_per_epoch, params, state.fork)
    elif is_testing_max_length:
        params = param_mapper(max_indices_per_slashable_vote, params)

    else:
        params = param_mapper(params)
    _run_verify_slashable_vote(
        slots_per_epoch,
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
        slots_per_epoch,
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

    message_hashes = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    valid_params = _correct_slashable_attestation_params(
        slots_per_epoch,
        num_validators,
        sample_slashable_attestation_params,
        message_hashes,
        privkeys,
        state.fork,
    )
    _run_verify_slashable_vote(
        slots_per_epoch,
        valid_params,
        state,
        max_indices_per_slashable_vote,
        True,
    )
