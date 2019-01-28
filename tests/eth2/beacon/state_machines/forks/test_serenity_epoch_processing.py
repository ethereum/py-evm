import pytest

from eth._utils.numeric import (
    int_to_bytes32,
)
from eth.constants import (
    ZERO_HASH32,
)

from eth2._utils.tuple import (
    update_tuple_item,
)
from eth2.beacon.helpers import (
    get_current_epoch_committee_count_per_slot,
)
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.state_machines.forks.serenity.epoch_processing import (
    _check_if_update_validator_registry,
    process_final_updates,
    process_validator_registry,
)


@pytest.mark.parametrize(
    (
        'num_validators, epoch_length, target_committee_size, shard_count, state_slot,'
        'validator_registry_update_slot,'
        'finalized_slot,'
        'has_crosslink,'
        'crosslink_slot,'
        'expected_need_to_update,'
    ),
    [
        # state.finalized_slot <= state.validator_registry_update_slot
        (
            40, 4, 2, 2, 16,
            4, 4, False, 0, False
        ),
        # state.latest_crosslinks[shard].slot <= state.validator_registry_update_slot
        (
            40, 4, 2, 2, 16,
            4, 8, True, 0, False,
        ),
        # state.finalized_slot > state.validator_registry_update_slot and
        # state.latest_crosslinks[shard].slot > state.validator_registry_update_slot
        (
            40, 4, 2, 2, 16,
            4, 8, True, 8, True,
        ),
    ]
)
def test_check_if_update_validator_registry(genesis_state,
                                            state_slot,
                                            validator_registry_update_slot,
                                            finalized_slot,
                                            has_crosslink,
                                            crosslink_slot,
                                            expected_need_to_update,
                                            config):
    state = genesis_state.copy(
        slot=state_slot,
        finalized_slot=finalized_slot,
        validator_registry_update_slot=validator_registry_update_slot,
    )
    if has_crosslink:
        crosslink = CrosslinkRecord(
            slot=crosslink_slot,
            shard_block_root=ZERO_HASH32,
        )
        latest_crosslinks = state.latest_crosslinks
        for shard in range(config.SHARD_COUNT):
            latest_crosslinks = update_tuple_item(
                latest_crosslinks,
                shard,
                crosslink,
            )
        state = state.copy(
            latest_crosslinks=latest_crosslinks,
        )

    need_to_update, num_shards_in_committees = _check_if_update_validator_registry(state, config)

    assert need_to_update == expected_need_to_update
    if expected_need_to_update:
        expected_num_shards_in_committees = get_current_epoch_committee_count_per_slot(
            state,
            shard_count=config.SHARD_COUNT,
            epoch_length=config.EPOCH_LENGTH,
            target_committee_size=config.TARGET_COMMITTEE_SIZE,
        ) * config.EPOCH_LENGTH
        assert num_shards_in_committees == expected_num_shards_in_committees
    else:
        assert num_shards_in_committees == 0


@pytest.mark.parametrize(
    (
        'num_validators, epoch_length, target_committee_size, shard_count,'
        'latest_randao_mixes_length, seed_lookahead, state_slot,'
        'need_to_update,'
        'num_shards_in_committees,'
        'validator_registry_update_slot,'
        'current_epoch_calculation_slot,'
        'latest_randao_mixes,'
        'expected_current_epoch_calculation_slot,'
        'expected_current_epoch_randao_mix,'
    ),
    [
        (
            40, 4, 2, 2,
            2**10, 4, 20,
            False,
            10,
            16,  # (state.slot - state.validator_registry_update_slot) EPOCH_LENGTH is power of two
            0,
            [int_to_bytes32(i) for i in range(2**10)],
            20,  # expected current_epoch_calculation_slot is state.slot
            int_to_bytes32((20 - 4) % 2**10),  # latest_randao_mixes[(result_state.current_epoch_calculation_slot - SEED_LOOKAHEAD) % LATEST_RANDAO_MIXES_LENGTH]  # noqa: E501
        ),
        (
            40, 4, 2, 2,
            2**10, 4, 20,
            False,
            10,
            8,  # (state.slot - state.validator_registry_update_slot) EPOCH_LENGTH != power of two
            0,
            [int_to_bytes32(i) for i in range(2**10)],
            0,  # expected current_epoch_calculation_slot is state.slot
            int_to_bytes32(0),
        ),
    ]
)
def test_process_validator_registry(monkeypatch,
                                    genesis_state,
                                    state_slot,
                                    need_to_update,
                                    num_shards_in_committees,
                                    validator_registry_update_slot,
                                    current_epoch_calculation_slot,
                                    latest_randao_mixes,
                                    expected_current_epoch_calculation_slot,
                                    expected_current_epoch_randao_mix,
                                    config):
    from eth2.beacon.state_machines.forks.serenity import epoch_processing

    def mock_check_if_update_validator_registry(state, config):
        return need_to_update, num_shards_in_committees

    monkeypatch.setattr(
        epoch_processing,
        '_check_if_update_validator_registry',
        mock_check_if_update_validator_registry
    )

    state = genesis_state.copy(
        slot=state_slot,
        validator_registry_update_slot=validator_registry_update_slot,
        current_epoch_calculation_slot=current_epoch_calculation_slot,
        latest_randao_mixes=latest_randao_mixes,
    )

    result_state = process_validator_registry(state, config)

    assert result_state.previous_epoch_calculation_slot == state.current_epoch_start_shard
    assert result_state.previous_epoch_start_shard == state.current_epoch_start_shard
    assert result_state.previous_epoch_randao_mix == state.current_epoch_randao_mix

    if need_to_update:
        assert result_state.current_epoch_calculation_slot == state_slot
        # TODO: Add test for validator registry updates
    else:
        assert (
            result_state.current_epoch_calculation_slot ==
            expected_current_epoch_calculation_slot
        )
        assert result_state.current_epoch_randao_mix == expected_current_epoch_randao_mix


@pytest.mark.parametrize(
    (
        'num_validators,'
        'state_slot,'
        'attestation_slot,'
        'len_latest_attestations,'
        'expected_result_len_latest_attestations,'
        'epoch_length'
    ),
    [
        (10, 4, 4, 2, 2, 4),  # attestation.data.slot >= state.slot - config.EPOCH_LENGTH, -> expected_result_len_latest_attestations = len_latest_attestations  # noqa: E501
        (10, 8, 4, 2, 2, 4),  # attestation.data.slot >= state.slot - config.EPOCH_LENGTH, -> expected_result_len_latest_attestations = len_latest_attestations  # noqa: E501
        (10, 16, 4, 2, 0, 4),  # attestation.data.slot < state.slot - config.EPOCH_LENGTH, -> expected_result_len_latest_attestations = 0  # noqa: E501
    ]
)
def test_process_final_updates(genesis_state,
                               state_slot,
                               attestation_slot,
                               len_latest_attestations,
                               expected_result_len_latest_attestations,
                               config,
                               sample_attestation_params):
    state = genesis_state.copy(
        slot=state_slot,
    )
    epoch = state.slot // config.EPOCH_LENGTH
    current_index = (epoch + 1) % config.LATEST_PENALIZED_EXIT_LENGTH
    previous_index = epoch % config.LATEST_PENALIZED_EXIT_LENGTH

    # Assume `len_latest_attestations` attestations in state.latest_attestations
    # with attestation.data.slot = attestation_slot
    attestation = Attestation(**sample_attestation_params)
    latest_attestations = [
        attestation.copy(
            data=attestation.data.copy(
                slot=attestation_slot
            )
        )
        for i in range(len_latest_attestations)
    ]

    # Fill latest_penalized_balances
    penalized_balance_of_previous_epoch = 100
    latest_penalized_balances = update_tuple_item(
        state.latest_penalized_balances,
        previous_index,
        penalized_balance_of_previous_epoch,
    )
    state = state.copy(
        latest_penalized_balances=latest_penalized_balances,
        latest_attestations=latest_attestations,
    )

    result_state = process_final_updates(state, config)

    assert (
        result_state.latest_penalized_balances[current_index] ==
        penalized_balance_of_previous_epoch
    )

    assert len(result_state.latest_attestations) == expected_result_len_latest_attestations
    for attestation in result_state.latest_attestations:
        assert attestation.data.slot >= state_slot - config.EPOCH_LENGTH
