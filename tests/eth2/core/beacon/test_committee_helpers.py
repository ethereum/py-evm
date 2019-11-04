import random

import pytest

from eth2.beacon.committee_helpers import (
    compute_proposer_index,
    get_beacon_committee,
    get_beacon_proposer_index,
    get_committee_count_at_slot,
)
from eth2.configs import CommitteeConfig


@pytest.mark.parametrize(
    (
        "validator_count,"
        "slots_per_epoch,"
        "target_committee_size,"
        "max_committees_per_slot,"
        "expected_committee_count"
    ),
    [
        # MAX_COMMITTEES_PER_SLOT // SLOTS_PER_EPOCH
        (1000, 20, 10, 50, 40),
        # active_validator_count // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE
        (500, 20, 10, 100, 40),
        # 1
        (20, 10, 3, 10, 10),
        # 1
        (40, 5, 10, 5, 5),
    ],
)
def test_get_committee_count_at_slot(
    validator_count,
    slots_per_epoch,
    target_committee_size,
    max_committees_per_slot,
    expected_committee_count,
    genesis_state,
):
    state = genesis_state
    assert expected_committee_count // slots_per_epoch == get_committee_count_at_slot(
        state,
        state.slot,
        max_committees_per_slot=max_committees_per_slot,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )


SOME_SEED = b"\x33" * 32


def test_compute_proposer_index(genesis_validators, config):
    proposer_index = random.randrange(0, len(genesis_validators))

    validators = tuple()
    # NOTE: validators supplied to ``compute_proposer_index``
    # should at a minimum have 17 ETH as ``effective_balance``.
    # Using 1 ETH should maintain the same spirit of the test and
    # ensure we can know the likely candidate ahead of time.
    one_eth_in_gwei = 1 * 10 ** 9
    for index, validator in enumerate(genesis_validators):
        if index == proposer_index:
            validators += (validator,)
        else:
            validators += (validator.copy(effective_balance=one_eth_in_gwei),)

    assert (
        compute_proposer_index(
            validators,
            range(len(validators)),
            SOME_SEED,
            config.MAX_EFFECTIVE_BALANCE,
            config.SHUFFLE_ROUND_COUNT,
        )
        == proposer_index
    )


def _invalidate_all_but_proposer(proposer_index, index, validator):
    if proposer_index == index:
        return validator
    else:
        return validator.copy(effective_balance=-1)


@pytest.mark.parametrize(("validator_count,"), [(1000)])
def test_get_beacon_proposer_index(genesis_state, config):
    state = genesis_state
    some_validator_index = random.sample(range(len(state.validators)), 1)[0]

    state = state.copy(
        validators=tuple(
            _invalidate_all_but_proposer(some_validator_index, index, validator)
            for index, validator in enumerate(state.validators)
        )
    )

    assert (
        get_beacon_proposer_index(state, CommitteeConfig(config))
        == some_validator_index
    )


@pytest.mark.parametrize(("validator_count,"), [(1000)])
def test_get_beacon_committee(genesis_state, config):
    state = genesis_state
    indices = tuple()
    epoch_start_slot = state.slot

    for slot in range(epoch_start_slot, epoch_start_slot + config.SLOTS_PER_EPOCH):
        committees_at_slot = get_committee_count_at_slot(
            state,
            slot,
            config.MAX_COMMITTEES_PER_SLOT,
            config.SLOTS_PER_EPOCH,
            config.TARGET_COMMITTEE_SIZE,
        )
        for committee_index in range(committees_at_slot):
            some_committee = get_beacon_committee(
                state, slot, committee_index, CommitteeConfig(config)
            )
            indices += tuple(some_committee)

    assert set(indices) == set(range(len(genesis_state.validators)))
    assert len(indices) == len(genesis_state.validators)
