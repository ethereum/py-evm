from typing import (
    Sequence,
)

from eth2.configs import Eth2Config
from eth2.beacon.genesis import (
    genesis_state_with_active_index_roots,
    get_genesis_beacon_state,
)
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Timestamp,
)


def _check_distinct_pubkeys(validators: Sequence[Validator]) -> None:
    pubkeys = tuple(v.pubkey for v in validators)
    assert len(set(pubkeys)) == len(pubkeys)


def _check_no_missing_balances(validators: Sequence[Validator],
                               balances: Sequence[Gwei]) -> None:
    assert len(validators) == len(balances)


def _check_sufficient_balance(balances: Sequence[Gwei], threshold: Gwei) -> None:
    for balance in balances:
        if balance < threshold:
            assert False


def _check_activated_validators(validators: Sequence[Validator],
                                genesis_epoch: Epoch) -> None:
    for validator in validators:
        assert validator.activation_eligibility_epoch == genesis_epoch
        assert validator.activation_epoch == genesis_epoch


def _check_correct_eth1_data(eth1_data: Eth1Data,
                             validators: Sequence[Validator]) -> None:
    assert eth1_data.deposit_count == len(validators)


def create_mock_genesis_state_from_validators(genesis_time: Timestamp,
                                              genesis_eth1_data: Eth1Data,
                                              genesis_validators: Sequence[Validator],
                                              genesis_balances: Sequence[Gwei],
                                              config: Eth2Config) -> BeaconState:
    """
    Produce a valid genesis state without creating the
    corresponding deposits.

    Compare with ``eth2.beacon.genesis.get_genesis_beacon_state``.
    """
    # NOTE: does not handle nondistinct pubkeys at the moment
    _check_distinct_pubkeys(genesis_validators)
    _check_no_missing_balances(genesis_validators, genesis_balances)
    _check_sufficient_balance(genesis_balances, config.MAX_EFFECTIVE_BALANCE)
    _check_activated_validators(genesis_validators, config.GENESIS_EPOCH)
    _check_correct_eth1_data(genesis_eth1_data, genesis_validators)

    empty_state = get_genesis_beacon_state(
        genesis_deposits=tuple(),
        genesis_time=genesis_time,
        genesis_eth1_data=genesis_eth1_data,
        config=config,
    )

    state_with_validators = empty_state.copy(
        eth1_deposit_index=empty_state.eth1_deposit_index + len(genesis_validators),
        validators=genesis_validators,
        balances=genesis_balances,
    )

    return genesis_state_with_active_index_roots(
        state_with_validators,
        config,
    )
