import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
    get_epoch_committee_count,
)


@pytest.mark.parametrize(
    (
        'active_validator_count,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'expected_committee_count'
    ),
    [
        # SHARD_COUNT // SLOTS_PER_EPOCH
        (1000, 20, 10, 50, 40),
        # active_validator_count // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE
        (500, 20, 10, 100, 40),
        # 1
        (20, 10, 3, 10, 10),
        # 1
        (20, 10, 3, 5, 10),
        # 1
        (40, 5, 10, 2, 5),
    ],
)
def test_get_epoch_committee_count(
        active_validator_count,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        expected_committee_count):
    assert expected_committee_count == get_epoch_committee_count(
        active_validator_count=active_validator_count,
        shard_count=shard_count,
        slots_per_epoch=slots_per_epoch,
        target_committee_size=target_committee_size,
    )


# TODO(ralexstokes) clean up
@pytest.mark.parametrize(
    (
        'validator_count,'
        'slots_per_epoch,'
        'committee,'
        'slot,'
        'success,'
    ),
    [
        (
            100,
            64,
            (10, 11, 12),
            0,
            True,
        ),
        (
            100,
            64,
            (),
            0,
            False,
        ),
    ]
)
def test_get_beacon_proposer_index(monkeypatch,
                                   validator_count,
                                   slots_per_epoch,
                                   committee,
                                   slot,
                                   success,
                                   sample_state,
                                   genesis_epoch,
                                   target_committee_size,
                                   shard_count,
                                   committee_config):
    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config,
                                              registry_change=False):
        return (
            (committee, 1,),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )
    if success:
        proposer_index = get_beacon_proposer_index(
            sample_state,
            slot,
            committee_config,
            registry_change=registry_change,
        )
        assert proposer_index == committee[slot % len(committee)]
    else:
        with pytest.raises(ValidationError):
            get_beacon_proposer_index(
                sample_state,
                slot,
                committee_config,
                registry_change=registry_change,
            )
