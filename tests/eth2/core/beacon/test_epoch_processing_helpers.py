import random

import pytest

from eth2._utils.bitfield import get_empty_bitfield, set_voted
from eth2._utils.tuple import update_tuple_item
from eth2.beacon.committee_helpers import get_beacon_committee
from eth2.beacon.constants import FAR_FUTURE_EPOCH, GWEI_PER_ETH
from eth2.beacon.epoch_processing_helpers import (
    compute_activation_exit_epoch,
    decrease_balance,
    get_attesting_indices,
    get_base_reward,
    get_matching_head_attestations,
    get_matching_source_attestations,
    get_matching_target_attestations,
    get_unslashed_attesting_indices,
    get_validator_churn_limit,
    increase_balance,
)
from eth2.beacon.exceptions import InvalidEpochError
from eth2.beacon.helpers import compute_start_slot_at_epoch
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.checkpoints import Checkpoint
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.typing import Gwei
from eth2.configs import CommitteeConfig


@pytest.mark.parametrize(
    ("delta,"),
    [(1), (GWEI_PER_ETH), (2 * GWEI_PER_ETH), (32 * GWEI_PER_ETH), (33 * GWEI_PER_ETH)],
)
def test_increase_balance(genesis_state, delta):
    index = random.sample(range(len(genesis_state.validators)), 1)[0]
    prior_balance = genesis_state.balances[index]
    state = increase_balance(genesis_state, index, delta)
    assert state.balances[index] == Gwei(prior_balance + delta)


@pytest.mark.parametrize(
    ("delta,"),
    [
        (1),
        (GWEI_PER_ETH),
        (2 * GWEI_PER_ETH),
        (32 * GWEI_PER_ETH),
        (33 * GWEI_PER_ETH),
        (100 * GWEI_PER_ETH),
    ],
)
def test_decrease_balance(genesis_state, delta):
    index = random.sample(range(len(genesis_state.validators)), 1)[0]
    prior_balance = genesis_state.balances[index]
    state = decrease_balance(genesis_state, index, delta)
    assert state.balances[index] == Gwei(max(prior_balance - delta, 0))


@pytest.mark.parametrize(("validator_count,"), [(1000)])
def test_get_attesting_indices(genesis_state, config):
    state = genesis_state.copy(
        slot=compute_start_slot_at_epoch(3, config.SLOTS_PER_EPOCH)
    )
    target_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    target_slot = compute_start_slot_at_epoch(target_epoch, config.SLOTS_PER_EPOCH)
    committee_index = 0
    some_committee = get_beacon_committee(
        state, target_slot, committee_index, CommitteeConfig(config)
    )

    data = AttestationData(
        slot=target_slot, index=committee_index, target=Checkpoint(epoch=target_epoch)
    )
    some_subset_count = random.randrange(1, len(some_committee) // 2)
    some_subset = random.sample(some_committee, some_subset_count)

    bitfield = get_empty_bitfield(len(some_committee))
    for i, index in enumerate(some_committee):
        if index in some_subset:
            bitfield = set_voted(bitfield, i)

    indices = get_attesting_indices(state, data, bitfield, CommitteeConfig(config))

    assert set(indices) == set(some_subset)
    assert len(indices) == len(some_subset)


def test_compute_activation_exit_epoch(max_seed_lookahead):
    epoch = random.randrange(0, FAR_FUTURE_EPOCH)
    entry_exit_effect_epoch = compute_activation_exit_epoch(epoch, max_seed_lookahead)
    assert entry_exit_effect_epoch == (epoch + 1 + max_seed_lookahead)


@pytest.mark.parametrize(
    (
        "validator_count,"
        "churn_limit_quotient,"
        "min_per_epoch_churn_limit,"
        "expected_churn_limit,"
    ),
    [
        # Too few validators
        (5, 100, 32, 32),
        # Enough validators
        (100, 1, 5, 100),
    ],
)
def test_get_validator_churn_limit(genesis_state, expected_churn_limit, config):
    assert get_validator_churn_limit(genesis_state, config) == expected_churn_limit


@pytest.mark.parametrize(
    ("current_epoch," "target_epoch," "success,"),
    [(40, 40, True), (40, 39, True), (40, 38, False), (40, 41, False)],
)
def test_get_matching_source_attestations(
    genesis_state, current_epoch, target_epoch, success, config
):
    state = genesis_state.copy(
        slot=compute_start_slot_at_epoch(current_epoch, config.SLOTS_PER_EPOCH),
        current_epoch_attestations=tuple(
            PendingAttestation(
                data=AttestationData(
                    beacon_block_root=current_epoch.to_bytes(32, "little")
                )
            )
        ),
        previous_epoch_attestations=tuple(
            PendingAttestation(
                data=AttestationData(
                    beacon_block_root=(current_epoch - 1).to_bytes(32, "little")
                )
            )
        ),
    )

    if success:
        attestations = get_matching_source_attestations(state, target_epoch, config)
    else:
        with pytest.raises(InvalidEpochError):
            get_matching_source_attestations(state, target_epoch, config)
        return

    if current_epoch == target_epoch:
        assert attestations == state.current_epoch_attestations
    else:
        assert attestations == state.previous_epoch_attestations


def test_get_matching_target_attestations(genesis_state, config):
    some_epoch = config.GENESIS_EPOCH + 20
    some_slot = compute_start_slot_at_epoch(some_epoch, config.SLOTS_PER_EPOCH)
    some_target_root = b"\x33" * 32
    target_attestations = tuple(
        (
            PendingAttestation(
                data=AttestationData(target=Checkpoint(root=some_target_root))
            )
            for _ in range(3)
        )
    )
    current_epoch_attestations = target_attestations + tuple(
        (
            PendingAttestation(
                data=AttestationData(target=Checkpoint(root=b"\x44" * 32))
            )
            for _ in range(3)
        )
    )
    state = genesis_state.copy(
        slot=some_slot + 1,
        block_roots=update_tuple_item(
            genesis_state.block_roots,
            some_slot % config.SLOTS_PER_HISTORICAL_ROOT,
            some_target_root,
        ),
        current_epoch_attestations=current_epoch_attestations,
    )

    attestations = get_matching_target_attestations(state, some_epoch, config)

    assert attestations == target_attestations


@pytest.mark.parametrize(("validator_count,"), [(1000)])
def test_get_matching_head_attestations(genesis_state, config):
    some_epoch = config.GENESIS_EPOCH + 20
    some_slot = (
        compute_start_slot_at_epoch(some_epoch, config.SLOTS_PER_EPOCH)
        + config.SLOTS_PER_EPOCH // 4
    )
    some_target_root = b"\x33" * 32
    target_attestations = tuple(
        (
            PendingAttestation(
                data=AttestationData(
                    slot=some_slot - 1,
                    index=0,
                    beacon_block_root=some_target_root,
                    target=Checkpoint(epoch=some_epoch - 1),
                )
            )
            for i in range(3)
        )
    )
    current_epoch_attestations = target_attestations + tuple(
        (
            PendingAttestation(
                data=AttestationData(
                    beacon_block_root=b"\x44" * 32,
                    target=Checkpoint(epoch=some_epoch - 1),
                )
            )
            for _ in range(3)
        )
    )
    state = genesis_state.copy(
        slot=some_slot,
        block_roots=tuple(
            some_target_root for _ in range(config.SLOTS_PER_HISTORICAL_ROOT)
        ),
        current_epoch_attestations=current_epoch_attestations,
    )

    attestations = get_matching_head_attestations(state, some_epoch, config)

    assert attestations == target_attestations


@pytest.mark.parametrize(("validator_count,"), [(1000)])
def test_get_unslashed_attesting_indices(genesis_state, config):
    state = genesis_state.copy(
        slot=compute_start_slot_at_epoch(3, config.SLOTS_PER_EPOCH)
    )
    target_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    target_slot = compute_start_slot_at_epoch(target_epoch, config.SLOTS_PER_EPOCH)
    committee_index = 0
    some_committee = get_beacon_committee(
        state, target_slot, committee_index, CommitteeConfig(config)
    )

    data = AttestationData(
        slot=state.slot, index=committee_index, target=Checkpoint(epoch=target_epoch)
    )
    some_subset_count = random.randrange(1, len(some_committee) // 2)
    some_subset = random.sample(some_committee, some_subset_count)

    bitfield = get_empty_bitfield(len(some_committee))
    for i, index in enumerate(some_committee):
        if index in some_subset:
            if random.choice([True, False]):
                state = state.update_validator_with_fn(
                    index, lambda v, *_: v.copy(slashed=True)
                )
            bitfield = set_voted(bitfield, i)

    some_subset = tuple(
        filter(lambda index: not state.validators[index].slashed, some_subset)
    )

    indices = get_unslashed_attesting_indices(
        state,
        (PendingAttestation(data=data, aggregation_bits=bitfield),),
        CommitteeConfig(config),
    )

    assert set(indices) == set(some_subset)
    assert len(indices) == len(some_subset)


def test_get_base_reward(genesis_state, config):
    assert get_base_reward(genesis_state, 0, config) == 905097
