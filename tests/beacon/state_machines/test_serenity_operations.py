import pytest

from eth_utils import (
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth.beacon.helpers import (
    get_block_root,
)

from eth.beacon.types.attestation_data import AttestationData
from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.blocks import BeaconBlockBody
from eth.beacon.state_machines.forks.serenity.operations import (
    process_attestations,
)


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
                              create_mock_signed_attestation,
                              success):

    attestation_slot = 0
    current_slot = attestation_slot + config.MIN_ATTESTATION_INCLUSION_DELAY
    state = genesis_state.copy(
        slot=current_slot,
    )

    attestations = []
    for shard_committee in state.shard_committees_at_slots[attestation_slot]:
        # have 0th committee member sign
        voting_committee_indices = [0]
        latest_crosslink_root = state.latest_crosslinks[shard_committee.shard].shard_block_root

        assert len(shard_committee.committee) > 0
        attestation_data = AttestationData(**sample_attestation_data_params).copy(
            slot=attestation_slot,
            shard=shard_committee.shard,
            justified_slot=state.previous_justified_slot,
            justified_block_root=get_block_root(
                state.latest_block_roots,
                state.slot,
                state.previous_justified_slot,
            ),
            latest_crosslink_root=latest_crosslink_root,
            shard_block_root=ZERO_HASH32,
        )

        attestations.append(
            create_mock_signed_attestation(
                state,
                shard_committee,
                voting_committee_indices,
                attestation_data,
            )
        )

    assert len(attestations) > 0

    if not success:
        # create invalid attestation in the future
        bad_attestation_data = AttestationData(**sample_attestation_data_params).copy(
            slot=state.slot + 10,
        )
        attestations.append(
            create_mock_signed_attestation(
                state,
                state.shard_committees_at_slots[attestation_slot][0],
                [0],
                bad_attestation_data,
            )
        )

    block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
        attestations=attestations,
    )
    block = BaseBeaconBlock(**sample_beacon_block_params).copy(
        slot=current_slot,
        body=block_body
    )

    if success:
        new_state = process_attestations(
            state,
            block,
            config
        )

        assert len(new_state.latest_attestations) == len(attestations)
    else:
        with pytest.raises(ValidationError):
            new_state = process_attestations(
                state,
                block,
                config
            )
