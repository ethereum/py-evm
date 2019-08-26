import random

from eth_utils.toolz import first, groupby, update_in
import pytest

from eth2.beacon.committee_helpers import get_beacon_proposer_index
from eth2.beacon.constants import FAR_FUTURE_EPOCH
from eth2.beacon.epoch_processing_helpers import (
    compute_activation_exit_epoch,
    get_validator_churn_limit,
)
from eth2.beacon.helpers import compute_start_slot_of_epoch
from eth2.beacon.tools.builder.initializer import create_mock_validator
from eth2.beacon.validator_status_helpers import (
    _compute_exit_queue_epoch,
    _set_validator_slashed,
    activate_validator,
    initiate_exit_for_validator,
    slash_validator,
)
from eth2.configs import CommitteeConfig


@pytest.mark.parametrize(("is_already_activated,"), [(True), (False)])
def test_activate_validator(
    genesis_state, is_already_activated, validator_count, pubkeys, config
):
    some_future_epoch = config.GENESIS_EPOCH + random.randrange(1, 2 ** 32)

    if is_already_activated:
        assert validator_count > 0
        some_validator = genesis_state.validators[0]
        assert some_validator.activation_eligibility_epoch == config.GENESIS_EPOCH
        assert some_validator.activation_epoch == config.GENESIS_EPOCH
    else:
        some_validator = create_mock_validator(
            pubkeys[: validator_count + 1], config, is_active=is_already_activated
        )
        assert some_validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH
        assert some_validator.activation_epoch == FAR_FUTURE_EPOCH
    assert not some_validator.slashed

    activated_validator = activate_validator(some_validator, some_future_epoch)
    assert activated_validator.activation_eligibility_epoch == some_future_epoch
    assert activated_validator.activation_epoch == some_future_epoch
    assert not activated_validator.slashed


@pytest.mark.parametrize(
    ("is_delayed_exit_epoch_the_maximum_exit_queue_epoch"), [(True,), (False,)]
)
@pytest.mark.parametrize(("is_churn_limit_met"), [(True,), (False,)])
def test_compute_exit_queue_epoch(
    genesis_state,
    is_delayed_exit_epoch_the_maximum_exit_queue_epoch,
    is_churn_limit_met,
    config,
):
    state = genesis_state
    for index in random.sample(
        range(len(state.validators)), len(state.validators) // 4
    ):
        some_future_epoch = config.GENESIS_EPOCH + random.randrange(1, 2 ** 32)
        state = state.update_validator_with_fn(
            index, lambda validator, *_: validator.copy(exit_epoch=some_future_epoch)
        )

    if is_delayed_exit_epoch_the_maximum_exit_queue_epoch:
        expected_candidate_exit_queue_epoch = compute_activation_exit_epoch(
            state.current_epoch(config.SLOTS_PER_EPOCH), config.ACTIVATION_EXIT_DELAY
        )
        for index, validator in enumerate(state.validators):
            if validator.exit_epoch == FAR_FUTURE_EPOCH:
                continue
            some_prior_epoch = random.randrange(
                config.GENESIS_EPOCH, expected_candidate_exit_queue_epoch
            )
            state = state.update_validator_with_fn(
                index, lambda validator, *_: validator.copy(exit_epoch=some_prior_epoch)
            )
            validator = state.validators[index]
            assert expected_candidate_exit_queue_epoch >= validator.exit_epoch
    else:
        expected_candidate_exit_queue_epoch = -1
        for validator in state.validators:
            if validator.exit_epoch == FAR_FUTURE_EPOCH:
                continue
            if validator.exit_epoch > expected_candidate_exit_queue_epoch:
                expected_candidate_exit_queue_epoch = validator.exit_epoch
        assert expected_candidate_exit_queue_epoch >= config.GENESIS_EPOCH

    if is_churn_limit_met:
        churn_limit = 0
        expected_exit_queue_epoch = expected_candidate_exit_queue_epoch + 1
    else:
        # add more validators to the queued epoch to make the test less trivial
        # with the setup so far, it is likely that the queue in the target epoch is size 1.
        queued_validators = {
            index: validator
            for index, validator in state.validators
            if validator.exit_epoch == expected_candidate_exit_queue_epoch
        }
        additional_queued_validator_count = random.randrange(
            len(queued_validators), len(state.validators)
        )
        unqueued_validators = tuple(
            v for v in state.validators if v.exit_epoch == FAR_FUTURE_EPOCH
        )
        for index in random.sample(
            range(len(unqueued_validators)), additional_queued_validator_count
        ):
            state = state.update_validator_with_fn(
                index,
                lambda validator, *_: validator.copy(
                    exit_epoch=expected_candidate_exit_queue_epoch
                ),
            )

        all_queued_validators = tuple(
            v
            for v in state.validators
            if v.exit_epoch == expected_candidate_exit_queue_epoch
        )
        churn_limit = len(all_queued_validators) + 1

        expected_exit_queue_epoch = expected_candidate_exit_queue_epoch

    assert (
        _compute_exit_queue_epoch(state, churn_limit, config)
        == expected_exit_queue_epoch
    )


@pytest.mark.parametrize(("is_already_exited,"), [(True), (False)])
def test_initiate_validator_exit(genesis_state, is_already_exited, config):
    state = genesis_state
    index = random.choice(range(len(state.validators)))
    validator = state.validators[index]
    assert not validator.slashed
    assert validator.activation_epoch == config.GENESIS_EPOCH
    assert validator.activation_eligibility_epoch == config.GENESIS_EPOCH
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    assert validator.withdrawable_epoch == FAR_FUTURE_EPOCH

    if is_already_exited:
        churn_limit = get_validator_churn_limit(state, config)
        exit_queue_epoch = _compute_exit_queue_epoch(state, churn_limit, config)
        validator = validator.copy(
            exit_epoch=exit_queue_epoch,
            withdrawable_epoch=exit_queue_epoch
            + config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY,
        )

    exited_validator = initiate_exit_for_validator(validator, state, config)

    if is_already_exited:
        assert exited_validator == validator
    else:
        churn_limit = get_validator_churn_limit(state, config)
        exit_queue_epoch = _compute_exit_queue_epoch(state, churn_limit, config)
        assert exited_validator.exit_epoch == exit_queue_epoch
        assert exited_validator.withdrawable_epoch == (
            exit_queue_epoch + config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        )


@pytest.mark.parametrize(("is_already_slashed,"), [(True), (False)])
def test_set_validator_slashed(
    genesis_state, is_already_slashed, validator_count, pubkeys, config
):
    some_future_epoch = config.GENESIS_EPOCH + random.randrange(1, 2 ** 32)

    assert len(genesis_state.validators) > 0
    some_validator = genesis_state.validators[0]

    if is_already_slashed:
        some_validator = some_validator.copy(
            slashed=True, withdrawable_epoch=some_future_epoch
        )
        assert some_validator.slashed
        assert some_validator.withdrawable_epoch == some_future_epoch
    else:
        assert not some_validator.slashed

    slashed_validator = _set_validator_slashed(
        some_validator, some_future_epoch, config.EPOCHS_PER_SLASHINGS_VECTOR
    )
    assert slashed_validator.slashed
    assert slashed_validator.withdrawable_epoch == max(
        slashed_validator.withdrawable_epoch,
        some_future_epoch + config.EPOCHS_PER_SLASHINGS_VECTOR,
    )


@pytest.mark.parametrize(("validator_count"), [(100)])
def test_slash_validator(genesis_state, config):
    some_epoch = (
        config.GENESIS_EPOCH
        + random.randrange(1, 2 ** 32)
        + config.EPOCHS_PER_SLASHINGS_VECTOR
    )
    earliest_slashable_epoch = some_epoch - config.EPOCHS_PER_SLASHINGS_VECTOR
    slashable_range = range(earliest_slashable_epoch, some_epoch)
    sampling_quotient = 4

    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(
            earliest_slashable_epoch, config.SLOTS_PER_EPOCH
        )
    )
    validator_count_to_slash = len(state.validators) // sampling_quotient
    assert validator_count_to_slash > 1
    validator_indices_to_slash = random.sample(
        range(len(state.validators)), validator_count_to_slash
    )
    # ensure case w/ one slashing in an epoch
    # by ignoring the first
    set_of_colluding_validators = validator_indices_to_slash[1:]
    # simulate multiple slashings in an epoch
    validators_grouped_by_coalition = groupby(
        lambda index: index % sampling_quotient, set_of_colluding_validators
    )
    coalition_count = len(validators_grouped_by_coalition)
    slashings = {
        epoch: coalition
        for coalition, epoch in zip(
            validators_grouped_by_coalition.values(),
            random.sample(slashable_range, coalition_count),
        )
    }
    another_slashing_epoch = first(random.sample(slashable_range, 1))
    while another_slashing_epoch in slashings:
        another_slashing_epoch += 1
    slashings[another_slashing_epoch] = (validator_indices_to_slash[0],)

    expected_slashings = {}
    expected_individual_penalties = {}
    for epoch, coalition in slashings.items():
        for index in coalition:
            validator = state.validators[index]
            assert validator.is_active(earliest_slashable_epoch)
            assert validator.exit_epoch == FAR_FUTURE_EPOCH
            assert validator.withdrawable_epoch == FAR_FUTURE_EPOCH

            expected_slashings = update_in(
                expected_slashings,
                [epoch],
                lambda balance: balance + state.validators[index].effective_balance,
                default=0,
            )
            expected_individual_penalties = update_in(
                expected_individual_penalties,
                [index],
                lambda penalty: (
                    penalty
                    + (
                        state.validators[index].effective_balance
                        // config.MIN_SLASHING_PENALTY_QUOTIENT
                    )
                ),
                default=0,
            )

    # emulate slashings across the current slashable range
    expected_proposer_rewards = {}
    for epoch, coalition in slashings.items():
        state = state.copy(
            slot=compute_start_slot_of_epoch(epoch, config.SLOTS_PER_EPOCH)
        )

        expected_total_slashed_balance = expected_slashings[epoch]
        proposer_index = get_beacon_proposer_index(state, CommitteeConfig(config))

        expected_proposer_rewards = update_in(
            expected_proposer_rewards,
            [proposer_index],
            lambda reward: reward
            + (expected_total_slashed_balance // config.WHISTLEBLOWER_REWARD_QUOTIENT),
            default=0,
        )
        for index in coalition:
            state = slash_validator(state, index, config)

    state = state.copy(
        slot=compute_start_slot_of_epoch(some_epoch, config.SLOTS_PER_EPOCH)
    )
    # verify result
    for epoch, coalition in slashings.items():
        for index in coalition:
            validator = state.validators[index]
            assert validator.exit_epoch != FAR_FUTURE_EPOCH
            assert validator.slashed
            assert validator.withdrawable_epoch == max(
                validator.exit_epoch + config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY,
                epoch + config.EPOCHS_PER_SLASHINGS_VECTOR,
            )

            slashed_epoch_index = epoch % config.EPOCHS_PER_SLASHINGS_VECTOR
            slashed_balance = state.slashings[slashed_epoch_index]
            assert slashed_balance == expected_slashings[epoch]
            assert state.balances[index] == (
                config.MAX_EFFECTIVE_BALANCE
                - expected_individual_penalties[index]
                + expected_proposer_rewards.get(index, 0)
            )

    for proposer_index, total_reward in expected_proposer_rewards.items():
        assert state.balances[proposer_index] == (
            total_reward
            + config.MAX_EFFECTIVE_BALANCE
            - expected_individual_penalties.get(proposer_index, 0)
        )
