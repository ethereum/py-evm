import pytest

from eth_utils import (
    denoms,
    ValidationError,
)

from eth.utils import bls

from eth.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth.beacon.enums import (
    SignatureDomain,
)
from eth.beacon.helpers import (
    get_domain,
)
from eth.beacon.deposit_helpers import (
    min_empty_validator_index,
    process_deposit,
    validate_proof_of_possession,
)
from eth.beacon.types.states import BeaconState
from eth.beacon.types.deposit_input import DepositInput
from eth.beacon.types.validator_records import ValidatorRecord


def sign_proof_of_possession(deposit_input, privkey, domain):
    return bls.sign(deposit_input.root, privkey, domain)


def make_deposit_input(pubkey, withdrawal_credentials, randao_commitment):
    return DepositInput(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        proof_of_possession=EMPTY_SIGNATURE,
    )


@pytest.mark.parametrize(
    "balance,"
    "latest_status_change_slot,"
    "zero_balance_validator_ttl,"
    "current_slot,"
    "expected",
    (
        (0, 1, 1, 2, 0),
        (1, 1, 1, 2, None),  # not (balance == 0)
        (0, 1, 1, 1, None),  # not (validator.latest_status_change_slot + zero_balance_validator_ttl <= current_slot) # noqa: E501
    ),
)
def test_min_empty_validator_index(sample_validator_record_params,
                                   balance,
                                   latest_status_change_slot,
                                   zero_balance_validator_ttl,
                                   current_slot,
                                   expected):
    validators = [
        ValidatorRecord(**sample_validator_record_params).copy(
            balance=balance,
            latest_status_change_slot=latest_status_change_slot,
        )
        for _ in range(10)
    ]

    result = min_empty_validator_index(
        validators=validators,
        current_slot=current_slot,
        zero_balance_validator_ttl=zero_balance_validator_ttl,
    )

    assert result == expected


@pytest.mark.parametrize(
    "expected",
    (
        (True),
        (ValidationError),
    ),
)
def test_validate_proof_of_possession(sample_beacon_state_params, pubkeys, privkeys, expected):
    state = BeaconState(**sample_beacon_state_params)

    privkey = privkeys[0]
    pubkey = pubkeys[0]
    withdrawal_credentials = b'\x34' * 32
    randao_commitment = b'\x56' * 32
    domain = get_domain(
        state.fork_data,
        state.slot,
        SignatureDomain.DOMAIN_DEPOSIT,
    )

    deposit_input = make_deposit_input(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
    )
    if expected is True:
        proof_of_possession = sign_proof_of_possession(deposit_input, privkey, domain)

        assert validate_proof_of_possession(
            state=state,
            pubkey=pubkey,
            proof_of_possession=proof_of_possession,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
        )
    else:
        proof_of_possession = b'\x11' * 32
        with pytest.raises(ValidationError):
            validate_proof_of_possession(
                state=state,
                pubkey=pubkey,
                proof_of_possession=proof_of_possession,
                withdrawal_credentials=withdrawal_credentials,
                randao_commitment=randao_commitment,
            )


def test_process_deposit(sample_beacon_state_params,
                         zero_balance_validator_ttl,
                         privkeys,
                         pubkeys):
    state = BeaconState(**sample_beacon_state_params).copy(
        slot=zero_balance_validator_ttl + 1,
        validator_registry=(),
    )

    privkey_1 = privkeys[0]
    pubkey_1 = pubkeys[0]
    deposit = 32 * denoms.gwei
    withdrawal_credentials = b'\x34' * 32
    randao_commitment = b'\x56' * 32
    domain = get_domain(
        state.fork_data,
        state.slot,
        SignatureDomain.DOMAIN_DEPOSIT,
    )

    deposit_input = make_deposit_input(
        pubkey=pubkey_1,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
    )
    proof_of_possession = sign_proof_of_possession(deposit_input, privkey_1, domain)
    # Add the first validator
    result_state, index = process_deposit(
        state=state,
        pubkey=pubkey_1,
        deposit=deposit,
        proof_of_possession=proof_of_possession,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        zero_balance_validator_ttl=zero_balance_validator_ttl,
    )

    assert len(result_state.validator_registry) == 1
    index = 0
    assert result_state.validator_registry[0].pubkey == pubkey_1
    assert result_state.validator_registry[index].withdrawal_credentials == withdrawal_credentials
    assert result_state.validator_registry[index].randao_commitment == randao_commitment
    assert result_state.validator_registry[index].balance == deposit
    # test immutable
    assert len(state.validator_registry) == 0

    # Add the second validator
    privkey_2 = privkeys[1]
    pubkey_2 = pubkeys[1]
    deposit_input = make_deposit_input(
        pubkey=pubkey_2,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
    )
    proof_of_possession = sign_proof_of_possession(deposit_input, privkey_2, domain)
    result_state, index = process_deposit(
        state=result_state,
        pubkey=pubkey_2,
        deposit=deposit,
        proof_of_possession=proof_of_possession,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        zero_balance_validator_ttl=zero_balance_validator_ttl,
    )
    assert len(result_state.validator_registry) == 2
    assert result_state.validator_registry[1].pubkey == pubkey_2

    # Force the first validator exited
    result_state = result_state.copy(
        validator_registry=(
            result_state.validator_registry[0].copy(
                balance=0,
                latest_status_change_slot=0,
            ),
            result_state.validator_registry[1],
        )
    )

    # Add the third validator
    privkey_3 = privkeys[2]
    pubkey_3 = pubkeys[2]
    deposit_input = make_deposit_input(
        pubkey=pubkey_3,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
    )
    proof_of_possession = sign_proof_of_possession(deposit_input, privkey_3, domain)
    result_state, index = process_deposit(
        state=result_state,
        pubkey=pubkey_3,
        deposit=deposit,
        proof_of_possession=proof_of_possession,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        zero_balance_validator_ttl=zero_balance_validator_ttl,
    )
    assert len(result_state.validator_registry) == 2
    assert result_state.validator_registry[0].pubkey == pubkey_3
