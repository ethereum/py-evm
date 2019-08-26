from eth_utils import ValidationError
import pytest

from eth2.beacon.deposit_helpers import process_deposit, validate_deposit_proof
from eth2.beacon.tools.builder.initializer import create_mock_deposit


@pytest.mark.parametrize(("success",), [(True,), (False,)])
def test_validate_deposit_proof(
    config, keymap, pubkeys, deposit_contract_tree_depth, genesis_state, success
):
    state = genesis_state
    withdrawal_credentials = b"\x34" * 32
    state, deposit = create_mock_deposit(
        state, pubkeys[0], keymap, withdrawal_credentials, config
    )

    if success:
        validate_deposit_proof(state, deposit, deposit_contract_tree_depth)
    else:
        deposit = deposit.copy(
            data=deposit.data.copy(withdrawal_credentials=b"\x23" * 32)
        )
        with pytest.raises(ValidationError):
            validate_deposit_proof(state, deposit, deposit_contract_tree_depth)


@pytest.mark.parametrize(("is_new_validator",), [(True,), (False,)])
def test_process_deposit(
    config,
    sample_beacon_state_params,
    keymap,
    genesis_state,
    validator_count,
    is_new_validator,
    pubkeys,
):
    state = genesis_state
    withdrawal_credentials = b"\x34" * 32
    if is_new_validator:
        validator_index = validator_count
    else:
        validator_index = validator_count - 1

    pubkey = pubkeys[validator_index]

    state, deposit = create_mock_deposit(
        state, pubkey, keymap, withdrawal_credentials, config
    )

    validator_count_before_deposit = state.validator_count

    result_state = process_deposit(state=state, deposit=deposit, config=config)

    # test immutability
    assert len(state.validators) == validator_count_before_deposit

    validator = result_state.validators[validator_index]
    if is_new_validator:
        assert len(result_state.validators) == len(state.validators) + 1
        assert validator.pubkey == pubkeys[validator_index]
        assert validator.withdrawal_credentials == withdrawal_credentials
        assert result_state.balances[validator_index] == config.MAX_EFFECTIVE_BALANCE
    else:
        assert len(result_state.validators) == len(state.validators)
        assert validator.pubkey == pubkeys[validator_index]
        assert (
            result_state.balances[validator_index] == 2 * config.MAX_EFFECTIVE_BALANCE
        )
