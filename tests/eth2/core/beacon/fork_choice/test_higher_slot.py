import pytest

from eth2.beacon.fork_choice.higher_slot import higher_slot_scoring
from eth2.beacon.types.blocks import BeaconBlock


@pytest.mark.parametrize("slot", (i for i in range(10)))
def test_higher_slot_fork_choice_scoring(sample_beacon_block_params, slot):
    block = BeaconBlock(**sample_beacon_block_params).copy(slot=slot)

    expected_score = slot

    score = higher_slot_scoring(block)

    assert score == expected_score
