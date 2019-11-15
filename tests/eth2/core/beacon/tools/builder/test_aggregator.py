import pytest

from eth2.beacon.committee_helpers import (
    compute_epoch_at_slot,
    iterate_committees_at_epoch,
)
from eth2.beacon.tools.builder.aggregator import (
    TARGET_AGGREGATORS_PER_COMMITTEE,
    is_aggregator,
    slot_signature,
)
from eth2.configs import CommitteeConfig


@pytest.mark.slow
@pytest.mark.parametrize(
    ("validator_count", "target_committee_size", "slots_per_epoch"), [(1000, 100, 10)]
)
def test_aggregate_votes(validator_count, privkeys, genesis_state, config):
    config = CommitteeConfig(config)
    state = genesis_state
    epoch = compute_epoch_at_slot(state.slot, config.SLOTS_PER_EPOCH)

    sum_aggregator_count = 0
    for committee, committee_index, slot in iterate_committees_at_epoch(
        state, epoch, config
    ):
        assert config.TARGET_COMMITTEE_SIZE == len(committee)
        aggregator_count = 0
        for index in range(validator_count):
            if index in committee:
                signature = slot_signature(genesis_state, slot, privkeys[index], config)
                attester_is_aggregator = is_aggregator(
                    state, slot, committee_index, signature, config
                )
                if attester_is_aggregator:
                    aggregator_count += 1
        assert aggregator_count > 0
        sum_aggregator_count += aggregator_count
    # The average aggregator count per slot should be around
    # `TARGET_AGGREGATORS_PER_COMMITTEE`.
    average_aggregator_count = sum_aggregator_count / config.SLOTS_PER_EPOCH
    assert (
        TARGET_AGGREGATORS_PER_COMMITTEE - 3
        < average_aggregator_count
        < TARGET_AGGREGATORS_PER_COMMITTEE + 3
    )
