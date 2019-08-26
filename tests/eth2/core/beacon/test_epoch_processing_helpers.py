import random

from eth_utils.toolz import random_sample
import pytest

from eth2._utils.bitfield import get_empty_bitfield, set_voted
from eth2._utils.tuple import update_tuple_item
from eth2.beacon.committee_helpers import get_crosslink_committee
from eth2.beacon.constants import FAR_FUTURE_EPOCH, GWEI_PER_ETH
from eth2.beacon.epoch_processing_helpers import (
    _find_winning_crosslink_and_attesting_indices_from_candidates,
    _get_attestations_for_shard,
    _get_attestations_for_valid_crosslink,
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
from eth2.beacon.helpers import compute_start_slot_of_epoch
from eth2.beacon.tools.builder.validator import mk_pending_attestation_from_committee
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.checkpoints import Checkpoint
from eth2.beacon.types.crosslinks import Crosslink
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
        slot=compute_start_slot_of_epoch(3, config.SLOTS_PER_EPOCH)
    )
    target_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    target_shard = (state.start_shard + 3) % config.SHARD_COUNT
    some_committee = get_crosslink_committee(
        state, target_epoch, target_shard, CommitteeConfig(config)
    )

    data = AttestationData(
        target=Checkpoint(epoch=target_epoch), crosslink=Crosslink(shard=target_shard)
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


def test_compute_activation_exit_epoch(activation_exit_delay):
    epoch = random.randrange(0, FAR_FUTURE_EPOCH)
    entry_exit_effect_epoch = compute_activation_exit_epoch(
        epoch, activation_exit_delay
    )
    assert entry_exit_effect_epoch == (epoch + 1 + activation_exit_delay)


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
        slot=compute_start_slot_of_epoch(current_epoch, config.SLOTS_PER_EPOCH),
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
    some_slot = compute_start_slot_of_epoch(some_epoch, config.SLOTS_PER_EPOCH)
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


def test_get_matching_head_attestations(genesis_state, config):
    some_epoch = config.GENESIS_EPOCH + 20
    some_slot = (
        compute_start_slot_of_epoch(some_epoch, config.SLOTS_PER_EPOCH)
        + config.SLOTS_PER_EPOCH // 4
    )
    some_target_root = b"\x33" * 32
    target_attestations = tuple(
        (
            PendingAttestation(
                data=AttestationData(
                    beacon_block_root=some_target_root,
                    target=Checkpoint(epoch=some_epoch - 1),
                    crosslink=Crosslink(shard=i),
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
        slot=some_slot - 1,
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
        slot=compute_start_slot_of_epoch(3, config.SLOTS_PER_EPOCH)
    )
    target_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    target_shard = (state.start_shard + 3) % config.SHARD_COUNT
    some_committee = get_crosslink_committee(
        state, target_epoch, target_shard, CommitteeConfig(config)
    )

    data = AttestationData(
        target=Checkpoint(epoch=target_epoch), crosslink=Crosslink(shard=target_shard)
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


@pytest.mark.parametrize(("validator_count,"), [(1000)])
def test_find_candidate_attestations_for_shard(genesis_state, config):
    some_epoch = config.GENESIS_EPOCH + 20
    # start on some shard and walk a subset of them
    some_shard = 3
    shard_offset = 24

    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(some_epoch, config.SLOTS_PER_EPOCH),
        start_shard=some_shard,
        current_crosslinks=tuple(
            Crosslink(shard=i, data_root=(i).to_bytes(32, "little"))
            for i in range(config.SHARD_COUNT)
        ),
    )

    # sample a subset of the shards to make attestations for
    some_shards_with_attestations = random.sample(
        range(some_shard, some_shard + shard_offset), shard_offset // 2
    )

    committee_and_shard_pairs = tuple(
        (
            get_crosslink_committee(
                state, some_epoch, some_shard + i, CommitteeConfig(config)
            ),
            some_shard + i,
        )
        for i in range(shard_offset)
        if some_shard + i in some_shards_with_attestations
    )

    pending_attestations = {
        shard: mk_pending_attestation_from_committee(
            state.current_crosslinks[shard], len(committee), shard
        )
        for committee, shard in committee_and_shard_pairs
    }

    # invalidate some crosslinks to test the crosslink filter
    some_crosslinks_to_mangle = random.sample(
        some_shards_with_attestations, len(some_shards_with_attestations) // 2
    )

    shards_with_valid_crosslinks = set(some_shards_with_attestations) - set(
        some_crosslinks_to_mangle
    )

    crosslinks = tuple()
    for shard in range(config.SHARD_COUNT):
        if shard in shards_with_valid_crosslinks:
            crosslinks += (state.current_crosslinks[shard],)
        else:
            crosslinks += (Crosslink(),)

    state = state.copy(current_crosslinks=crosslinks)

    # check around the range of shards we built up
    for shard in range(0, some_shard + shard_offset + 3):
        if shard in some_shards_with_attestations:
            attestations = _get_attestations_for_shard(
                pending_attestations.values(), shard
            )
            assert attestations == (pending_attestations[shard],)

            if shard in some_crosslinks_to_mangle:
                assert not _get_attestations_for_valid_crosslink(
                    pending_attestations.values(), state, shard, config
                )
            else:
                attestations = _get_attestations_for_valid_crosslink(
                    pending_attestations.values(), state, shard, config
                )
                assert attestations == (pending_attestations[shard],)
        else:
            assert not _get_attestations_for_shard(pending_attestations.values(), shard)
            assert not _get_attestations_for_valid_crosslink(
                pending_attestations.values(), state, shard, config
            )


@pytest.mark.parametrize(("validator_count,"), [(1000)])
@pytest.mark.parametrize(("number_of_candidates,"), [(0), (1), (3)])
def test_find_winning_crosslink_and_attesting_indices_from_candidates(
    genesis_state, number_of_candidates, config
):
    some_epoch = config.GENESIS_EPOCH + 20
    some_shard = 3

    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(some_epoch, config.SLOTS_PER_EPOCH),
        start_shard=some_shard,
        current_crosslinks=tuple(
            Crosslink(shard=i, data_root=(i).to_bytes(32, "little"))
            for i in range(config.SHARD_COUNT)
        ),
    )

    full_committee = get_crosslink_committee(
        state, some_epoch, some_shard, CommitteeConfig(config)
    )

    # break the committees up into different subsets to simulate different
    # attestations for the same crosslink
    committees = tuple(
        random_sample(len(full_committee) // number_of_candidates, full_committee)
        for _ in range(number_of_candidates)
    )
    seen = set()
    filtered_committees = tuple()
    for committee in committees:
        deduplicated_committee = tuple()
        for index in committee:
            if index in seen:
                pass
            else:
                seen.add(index)
                deduplicated_committee += (index,)
        filtered_committees += (deduplicated_committee,)

    candidates = tuple(
        mk_pending_attestation_from_committee(
            state.current_crosslinks[some_shard],
            len(full_committee),
            some_shard,
            target_epoch=some_epoch,
        )
        for committee in filtered_committees
    )

    if number_of_candidates == 0:
        expected_result = (Crosslink(), set())
    else:
        expected_result = (candidates[0].data.crosslink, set(sorted(full_committee)))

    result = _find_winning_crosslink_and_attesting_indices_from_candidates(
        state, candidates, config
    )
    assert result == expected_result


def test_get_base_reward(genesis_state, config):
    assert get_base_reward(genesis_state, 0, config) == 724077
