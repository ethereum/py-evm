from eth.beacon.state_machines.validation import (
    validate_proposer_signature,
)

from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.states import BeaconState

from tests.beacon.helpers import mock_validator_record
from tests.beacon.test_helpers import (
    get_sample_shard_committees_at_slots,
)


def test_validate_proposer_signature(
        beacon_chain_shard_number,
        epoch_length,
        sample_beacon_block_params,
        sample_beacon_state_params,
        sample_shard_committee_params):
    block = BaseBeaconBlock(**sample_beacon_block_params)
    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=[
            mock_validator_record(
                pubkey=0,
                max_deposit=0,
            )
            for _ in range(10)
        ],
        shard_committees_at_slots=get_sample_shard_committees_at_slots(
            num_slot=128,
            num_shard_committee_per_slot=10,
            sample_shard_committee_params=sample_shard_committee_params,
        ),
    )

    validate_proposer_signature(
        state,
        block,
        beacon_chain_shard_number,
        epoch_length,
    )
