import random

import pytest

from eth_utils import to_dict

from eth_utils.toolz import (
    first,
    keyfilter,
    merge,
    merge_with,
    second,
    sliding_window,
)

from eth2._utils import bitfield
from eth2.configs import CommitteeConfig
from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
    ZERO_HASH32,
)
from eth2.beacon.committee_helpers import (
    get_current_epoch_committee_count,
    get_crosslink_committees_at_slot,
    get_next_epoch_committee_count,
    get_previous_epoch_committee_count,
)
from eth2.beacon.helpers import (
    get_epoch_start_slot,
    slot_to_epoch,
)
from eth2.beacon.fork_choice.lmd_ghost import Store
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.crosslinks import Crosslink


def _mk_range_for_epoch(epoch, slots_per_epoch):
    start = get_epoch_start_slot(epoch, slots_per_epoch)
    return range(start, start + slots_per_epoch)


@to_dict
def _mk_attestations_for_epoch_by_count(number_of_committee_samples,
                                        epoch_range,
                                        state,
                                        config):
    for _ in range(number_of_committee_samples):
        slot = random.choice(epoch_range)
        crosslink_committees_at_slot = get_crosslink_committees_at_slot(
            state,
            slot,
            committee_config=CommitteeConfig(config),
        )
        committee, shard = random.choice(crosslink_committees_at_slot)
        attestation_data = AttestationData(
            slot=slot,
            beacon_block_root=ZERO_HASH32,
            source_epoch=0,
            source_root=ZERO_HASH32,
            target_root=ZERO_HASH32,
            shard=shard,
            previous_crosslink=Crosslink(
                epoch=0,
                crosslink_data_root=ZERO_HASH32,
            ),
            crosslink_data_root=ZERO_HASH32,
        )
        committee_count = len(committee)
        aggregation_bitfield = bitfield.get_empty_bitfield(committee_count)
        for index in range(committee_count):
            aggregation_bitfield = bitfield.set_voted(aggregation_bitfield, index)

        for index in committee:
            yield (
                index,
                (
                    slot,
                    (
                        aggregation_bitfield,
                        attestation_data,
                    ),
                ),
            )


def _extract_attestations_from_index_keying(values):
    results = ()
    for value in values:
        aggregation_bitfield, data = second(value)
        attestation = Attestation(
            aggregation_bitfield=aggregation_bitfield,
            data=data,
            custody_bitfield=bytes(),
            aggregate_signature=EMPTY_SIGNATURE,
        )
        if attestation not in results:
            results += (attestation,)
    return results


def _keep_by_latest_slot(values):
    """
    we get a sequence of (Slot, (Bitfield, AttestationData))
    and return the AttestationData with the highest slot
    """
    return max(values, key=first)[1][1]


def _find_collision(state, config, index=None, epoch=None):
    """
    Given a target epoch, make the attestation expected for the
    validator w/ the given index.
    """
    assert index is not None
    assert epoch is not None

    epoch_range = _mk_range_for_epoch(epoch, config.SLOTS_PER_EPOCH)

    for slot in epoch_range:
        crosslink_committees_at_slot = get_crosslink_committees_at_slot(
            state,
            slot,
            committee_config=CommitteeConfig(config),
        )

        for committee, shard in crosslink_committees_at_slot:
            if index in committee:
                attestation_data = AttestationData(
                    slot=slot,
                    beacon_block_root=ZERO_HASH32,
                    source_epoch=0,
                    source_root=ZERO_HASH32,
                    target_root=ZERO_HASH32,
                    shard=shard,
                    previous_crosslink=Crosslink(
                        epoch=0,
                        crosslink_data_root=ZERO_HASH32,
                    ),
                    crosslink_data_root=ZERO_HASH32,
                )
                committee_count = len(committee)
                aggregation_bitfield = bitfield.get_empty_bitfield(committee_count)
                for i in range(committee_count):
                    aggregation_bitfield = bitfield.set_voted(aggregation_bitfield, i)

                return {
                    index: (
                        slot, (aggregation_bitfield, attestation_data)
                    )
                    for index in committee
                }
    else:
        raise Exception("should have found a duplicate validator")


def _introduce_collisions(all_attestations_by_index,
                          state,
                          config):
    """
    Find some attestations for later epochs for the validators
    that are current attesting in each source of attestation.
    """
    collisions = (all_attestations_by_index[0],)
    for src, dst in sliding_window(2, all_attestations_by_index):
        if not src:
            # src can be empty at low validator count
            collisions += (dst,)
            continue
        src_index = random.choice(list(src.keys()))
        src_val = src[src_index]
        src_slot, _ = src_val
        src_epoch = slot_to_epoch(src_slot, config.SLOTS_PER_EPOCH)
        dst_epoch = src_epoch + 1

        collision = _find_collision(state, config, index=src_index, epoch=dst_epoch)
        collisions += (merge(dst, collision),)
    return collisions


@pytest.mark.parametrize(
    (
        "n",
    ),
    [
        (8,),     # low number of validators
        (128,),   # medium number of validators
        (1024,),  # high number of validators
    ]
)
@pytest.mark.parametrize(
    (
        "collisions",
    ),
    [
        (True,),
        (False,),
    ]
)
def test_store_get_latest_attestation(n_validators_state,
                                      empty_attestation_pool,
                                      config,
                                      collisions):
    """
    Given some attestations across the various sources, can we
    find the latest ones for each validator?
    """
    some_epoch = 3
    state = n_validators_state.copy(
        slot=get_epoch_start_slot(some_epoch, config.SLOTS_PER_EPOCH),
    )
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH)
    previous_epoch_range = _mk_range_for_epoch(previous_epoch, config.SLOTS_PER_EPOCH)
    previous_epoch_committee_count = get_previous_epoch_committee_count(
        state,
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )

    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    current_epoch_range = _mk_range_for_epoch(current_epoch, config.SLOTS_PER_EPOCH)
    current_epoch_committee_count = get_current_epoch_committee_count(
        state,
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )

    next_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    next_epoch_range = _mk_range_for_epoch(next_epoch, config.SLOTS_PER_EPOCH)
    next_epoch_committee_count = get_next_epoch_committee_count(
        state,
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )

    number_of_committee_samples = 4
    assert number_of_committee_samples <= previous_epoch_committee_count
    assert number_of_committee_samples <= current_epoch_committee_count
    assert number_of_committee_samples <= next_epoch_committee_count

    # prepare samples from previous epoch
    previous_epoch_attestations_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples,
        previous_epoch_range,
        state,
        config,
    )
    previous_epoch_attestations = _extract_attestations_from_index_keying(
        previous_epoch_attestations_by_index.values(),
    )

    # prepare samples from current epoch
    current_epoch_attestations_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples,
        current_epoch_range,
        state,
        config,
    )
    current_epoch_attestations_by_index = keyfilter(
        lambda index: index not in previous_epoch_attestations_by_index,
        current_epoch_attestations_by_index,
    )
    current_epoch_attestations = _extract_attestations_from_index_keying(
        current_epoch_attestations_by_index.values(),
    )

    # prepare samples for pool, taking half from the current epoch and half from the next epoch
    pool_attestations_in_current_epoch_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples // 2,
        current_epoch_range,
        state,
        config,
    )
    pool_attestations_in_next_epoch_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples // 2,
        next_epoch_range,
        state,
        config,
    )
    pool_attestations_by_index = merge(
        pool_attestations_in_current_epoch_by_index,
        pool_attestations_in_next_epoch_by_index,
    )
    pool_attestations_by_index = keyfilter(
        lambda index: (
            index not in previous_epoch_attestations_by_index or
            index not in current_epoch_attestations_by_index
        ),
        pool_attestations_by_index,
    )
    pool_attestations = _extract_attestations_from_index_keying(
        pool_attestations_by_index.values(),
    )

    all_attestations_by_index = (
        previous_epoch_attestations_by_index,
        current_epoch_attestations_by_index,
        pool_attestations_by_index,
    )

    if collisions:
        (
            previous_epoch_attestations_by_index,
            current_epoch_attestations_by_index,
            pool_attestations_by_index,
        ) = _introduce_collisions(
            all_attestations_by_index,
            state,
            config,
        )

        previous_epoch_attestations = _extract_attestations_from_index_keying(
            previous_epoch_attestations_by_index.values(),
        )
        current_epoch_attestations = _extract_attestations_from_index_keying(
            current_epoch_attestations_by_index.values(),
        )
        pool_attestations = _extract_attestations_from_index_keying(
            pool_attestations_by_index.values(),
        )

    # build expected results
    expected_index = merge_with(
        _keep_by_latest_slot,
        previous_epoch_attestations_by_index,
        current_epoch_attestations_by_index,
        pool_attestations_by_index,
    )

    # ensure we get the expected results
    state = state.copy(
        previous_epoch_attestations=previous_epoch_attestations,
        current_epoch_attestations=current_epoch_attestations,
    )

    pool = empty_attestation_pool
    for attestation in pool_attestations:
        pool.add(attestation)

    chain_db = None  # not relevant for this test
    store = Store(chain_db, state, pool, BeaconBlock, config)

    # sanity check
    assert expected_index.keys() == store._attestation_index.keys()

    for validator_index in range(len(state.validator_registry)):
        expected_attestation_data = expected_index.get(validator_index, None)
        stored_attestation_data = store._get_latest_attestation(validator_index)
        assert expected_attestation_data == stored_attestation_data
