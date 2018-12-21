import pytest

from eth_utils import (
    denoms,
    ValidationError,
)

from eth._utils import bls

from eth.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth.beacon.deposit_helpers import (
    add_pending_validator,
    get_min_empty_validator_index,
    process_deposit,
    validate_proof_of_possession,
)
from eth.beacon.enums import (
    SignatureDomain,
)
from eth.beacon.exceptions import (
    MinEmptyValidatorIndexNotFound,
)
from eth.beacon.helpers import (
    get_domain,
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
        (1, 1, 1, 2, MinEmptyValidatorIndexNotFound()),  # not (balance == 0)
        (0, 1, 1, 1, MinEmptyValidatorIndexNotFound()),  # not (validator.latest_status_change_slot + zero_balance_validator_ttl <= current_slot) # noqa: E501
    ),
)
def test_get_min_empty_validator_index(sample_validator_record_params,
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
    if isinstance(expected, Exception):
        with pytest.raises(MinEmptyValidatorIndexNotFound):
            get_min_empty_validator_index(
                validators=validators,
                current_slot=current_slot,
                zero_balance_validator_ttl=zero_balance_validator_ttl,
            )
    else:
        result = get_min_empty_validator_index(
            validators=validators,
            current_slot=current_slot,
            zero_balance_validator_ttl=zero_balance_validator_ttl,
        )
        assert result == expected


@pytest.mark.parametrize(
    "validator_registry_len,"
    "min_empty_validator_index_result,"
    "expected_index",
    (
        (10, 1, 1),
        (10, 5, 5),
        (10, None, 10),
    ),
)
def test_add_pending_validator(monkeypatch,
                               sample_beacon_state_params,
                               sample_validator_record_params,
                               validator_registry_len,
                               min_empty_validator_index_result,
                               expected_index):
    from eth.beacon import deposit_helpers

    def mock_get_min_empty_validator_index(validators,
                                           current_slot,
                                           zero_balance_validator_ttl):
        if min_empty_validator_index_result is None:
            raise MinEmptyValidatorIndexNotFound()
        else:
            return min_empty_validator_index_result

    monkeypatch.setattr(
        deposit_helpers,
        'get_min_empty_validator_index',
        mock_get_min_empty_validator_index
    )

    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=[
            ValidatorRecord(**sample_validator_record_params).copy(
                balance=100,
            )
            for _ in range(validator_registry_len)
        ]
    )
    validator = ValidatorRecord(**sample_validator_record_params).copy(
        balance=5566,
    )
    state, index = add_pending_validator(
        state,
        validator,
        zero_balance_validator_ttl=0,  # it's for `get_min_empty_validator_index`
    )
    assert index == expected_index
    assert state.validator_registry[index] == validator


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

        validate_proof_of_possession(
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

    # Force the first validator exited -> a empty slot in state.validator_registry.
    result_state = result_state.copy(
        validator_registry=(
            result_state.validator_registry[0].copy(
                balance=0,
                latest_status_change_slot=0,
            ),
            result_state.validator_registry[1],
        )
    )

    # Add the third validator.
    # Should overwrite previously exited validator.
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
    # Overwrite the second validator.
    assert len(result_state.validator_registry) == 2
    assert result_state.validator_registry[0].pubkey == pubkey_3
