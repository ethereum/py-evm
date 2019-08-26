import random

from eth_utils import ValidationError
import pytest

from eth2.beacon.committee_helpers import (
    _calculate_first_committee_at_slot,
    _find_proposer_in_committee,
    get_beacon_proposer_index,
    get_committee_count,
    get_committees_per_slot,
    get_crosslink_committee,
    get_shard_delta,
    get_start_shard,
)
from eth2.beacon.helpers import (
    compute_start_slot_of_epoch,
    get_active_validator_indices,
)
from eth2.configs import CommitteeConfig


@pytest.mark.parametrize(
    (
        "active_validator_count,"
        "slots_per_epoch,"
        "target_committee_size,"
        "shard_count,"
        "expected_committee_count"
    ),
    [
        # SHARD_COUNT // SLOTS_PER_EPOCH
        (1000, 20, 10, 50, 40),
        # active_validator_count // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE
        (500, 20, 10, 100, 40),
        # 1
        (20, 10, 3, 10, 10),
        # 1
        (40, 5, 10, 5, 5),
    ],
)
def test_get_committees_per_slot(
    active_validator_count,
    slots_per_epoch,
    target_committee_size,
    shard_count,
    expected_committee_count,
):
    assert expected_committee_count // slots_per_epoch == get_committees_per_slot(
        active_validator_count=active_validator_count,
        shard_count=shard_count,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )


@pytest.mark.parametrize(
    (
        "active_validator_count,"
        "slots_per_epoch,"
        "target_committee_size,"
        "shard_count,"
        "expected_committee_count"
    ),
    [
        # SHARD_COUNT // SLOTS_PER_EPOCH
        (1000, 20, 10, 50, 40),
        # active_validator_count // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE
        (500, 20, 10, 100, 40),
        # 1
        (20, 10, 3, 10, 10),
        # 1
        (40, 5, 10, 5, 5),
    ],
)
def test_get_committee_count(
    active_validator_count,
    slots_per_epoch,
    target_committee_size,
    shard_count,
    expected_committee_count,
):
    assert expected_committee_count == get_committee_count(
        active_validator_count=active_validator_count,
        shard_count=shard_count,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )


@pytest.mark.parametrize(
    (
        "validator_count,"
        "slots_per_epoch,"
        "target_committee_size,"
        "shard_count,"
        "expected_shard_delta,"
    ),
    [
        # SHARD_COUNT - SHARD_COUNT // SLOTS_PER_EPOCH
        (1000, 25, 5, 50, 50 - 50 // 20),
        # active_validator_count // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE
        (500, 20, 10, 100, 40),
    ],
)
def test_get_shard_delta(genesis_state, expected_shard_delta, config):
    state = genesis_state
    epoch = state.current_epoch(config.SLOTS_PER_EPOCH)

    assert get_shard_delta(state, epoch, config) == expected_shard_delta


@pytest.mark.parametrize(
    (
        "validator_count,"
        "slots_per_epoch,"
        "target_committee_size,"
        "shard_count,"
        "current_epoch,"
        "target_epoch,"
        "expected_epoch_start_shard,"
    ),
    [
        (1000, 25, 5, 50, 3, 2, 2),
        (1000, 25, 5, 50, 3, 3, 0),
        (1000, 25, 5, 50, 3, 4, 48),
        (1000, 25, 5, 50, 3, 5, None),
    ],
)
def test_get_start_shard(
    genesis_state, current_epoch, target_epoch, expected_epoch_start_shard, config
):
    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(current_epoch, config.SLOTS_PER_EPOCH)
    )

    if expected_epoch_start_shard is None:
        with pytest.raises(ValidationError):
            get_start_shard(state, target_epoch, CommitteeConfig(config))
    else:
        epoch_start_shard = get_start_shard(
            state, target_epoch, CommitteeConfig(config)
        )
        assert epoch_start_shard == expected_epoch_start_shard


SOME_SEED = b"\x33" * 32


def test_find_proposer_in_committee(genesis_validators, config):
    epoch = random.randrange(config.GENESIS_EPOCH, 2 ** 64)
    proposer_index = random.randrange(0, len(genesis_validators))

    validators = tuple()
    # NOTE: validators supplied to ``_find_proposer_in_committee``
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
        _find_proposer_in_committee(
            validators,
            range(len(validators)),
            epoch,
            SOME_SEED,
            config.MAX_EFFECTIVE_BALANCE,
        )
        == proposer_index
    )


def test_calculate_first_committee_at_slot(genesis_state, config):
    state = genesis_state
    slots_per_epoch = config.SLOTS_PER_EPOCH
    shard_count = config.SHARD_COUNT
    target_committee_size = config.TARGET_COMMITTEE_SIZE

    current_epoch = state.current_epoch(slots_per_epoch)

    active_validator_indices = get_active_validator_indices(
        state.validators, current_epoch
    )

    committees_per_slot = get_committees_per_slot(
        len(active_validator_indices),
        shard_count,
        slots_per_epoch,
        target_committee_size,
    )

    assert state.slot % config.SLOTS_PER_EPOCH == 0
    for slot in range(state.slot, state.slot + config.SLOTS_PER_EPOCH):
        offset = committees_per_slot * (slot % slots_per_epoch)
        shard = (get_start_shard(state, current_epoch, config) + offset) % shard_count
        committee = get_crosslink_committee(state, current_epoch, shard, config)

        assert committee == _calculate_first_committee_at_slot(
            state, slot, CommitteeConfig(config)
        )


def _invalidate_all_but_proposer(proposer_index, index, validator):
    if proposer_index == index:
        return validator
    else:
        return validator.copy(effective_balance=-1)


@pytest.mark.parametrize(("validator_count,"), [(1000)])
def test_get_beacon_proposer_index(genesis_state, config):
    state = genesis_state
    first_committee = _calculate_first_committee_at_slot(
        state, state.slot, CommitteeConfig(config)
    )
    some_validator_index = random.sample(first_committee, 1)[0]

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
def test_get_crosslink_committee(genesis_state, config):
    indices = tuple()
    for shard in range(
        get_shard_delta(genesis_state, config.GENESIS_EPOCH, CommitteeConfig(config))
    ):
        some_committee = get_crosslink_committee(
            genesis_state,
            genesis_state.current_epoch(config.SLOTS_PER_EPOCH),
            genesis_state.start_shard + shard,
            CommitteeConfig(config),
        )
        indices += tuple(some_committee)

    assert set(indices) == set(range(len(genesis_state.validators)))
    assert len(indices) == len(genesis_state.validators)
