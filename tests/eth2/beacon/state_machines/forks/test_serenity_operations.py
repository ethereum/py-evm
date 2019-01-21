import pytest

from eth_utils import (
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.helpers import (
    get_block_root,
    get_crosslink_committees_at_slot,
)

from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
    SerenityBeaconBlockBody,
)
from eth2.beacon.state_machines.forks.serenity.operations import (
    process_attestations,
)


@pytest.fixture
def create_mock_signed_attestations_at_slot(config,
                                            sample_attestation_data_params,
                                            create_mock_signed_attestation):
    def create_mock_signed_attestations_at_slot(state,
                                                attestation_slot):
        attestations = []
        shard_and_committees_at_slot = get_crosslink_committees_at_slot(
            state,
            slot=attestation_slot,
            epoch_length=config.EPOCH_LENGTH,
        )
        for crosslink_committee in shard_and_committees_at_slot:
            # have 0th committee member sign
            voting_committee_indices = [0]
            latest_crosslink_root = state.latest_crosslinks[
                crosslink_committee.shard].shard_block_root

            assert len(crosslink_committee.committee) > 0
            attestation_data = AttestationData(**sample_attestation_data_params).copy(
                slot=attestation_slot,
                shard=crosslink_committee.shard,
                justified_slot=state.previous_justified_slot,
                justified_block_root=get_block_root(
                    state,
                    state.previous_justified_slot,
                    config.LATEST_BLOCK_ROOTS_LENGTH,
                ),
                latest_crosslink_root=latest_crosslink_root,
                shard_block_root=ZERO_HASH32,
            )

            attestations.append(
                create_mock_signed_attestation(
                    state,
                    crosslink_committee,
                    voting_committee_indices,
                    attestation_data,
                )
            )
        return tuple(attestations)
    return create_mock_signed_attestations_at_slot


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'min_attestation_inclusion_delay,'
        'target_committee_size,'
        'shard_count,'
        'success,'
    ),
    [
        (10, 2, 1, 2, 2, True),
        (10, 2, 1, 2, 2, False),
        (40, 4, 2, 3, 5, True),
    ]
)
def test_process_attestations(genesis_state,
                              sample_attestation_data_params,
                              sample_beacon_block_params,
                              sample_beacon_block_body_params,
                              config,
                              create_mock_signed_attestations_at_slot,
                              success):

    attestation_slot = 0
    current_slot = attestation_slot + config.MIN_ATTESTATION_INCLUSION_DELAY
    state = genesis_state.copy(
        slot=current_slot,
    )

    attestations = create_mock_signed_attestations_at_slot(
        state,
        attestation_slot,
    )

    assert len(attestations) > 0

    if not success:
        # create invalid attestation in the future
        invalid_attestation_data = attestations[-1].data.copy(
            slot=state.slot + 10,
        )
        invalid_attestation = attestations[-1].copy(
            data=invalid_attestation_data,
        )
        attestations = attestations[:-1] + (invalid_attestation,)

    block_body = SerenityBeaconBlockBody(**sample_beacon_block_body_params).copy(
        attestations=attestations,
    )
    block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
        slot=current_slot,
        body=block_body,
    )

    if success:
        new_state = process_attestations(
            state,
            block,
            config,
        )

        assert len(new_state.latest_attestations) == len(attestations)
    else:
        with pytest.raises(ValidationError):
            process_attestations(
                state,
                block,
                config,
            )
