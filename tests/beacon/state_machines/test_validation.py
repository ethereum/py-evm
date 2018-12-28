import pytest

from eth_utils import (
    ValidationError,
)

from eth.beacon.enums import (
    SignatureDomain,
)

from eth.beacon.state_machines.validation import (
    validate_proposer_signature,
)

from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.proposal_signed_data import (
    ProposalSignedData,
)
from eth.beacon.types.states import BeaconState

from eth._utils import bls

from tests.beacon.helpers import mock_validator_record
from tests.beacon.test_helpers import (
    get_sample_shard_committees_at_slots,
)


@pytest.mark.parametrize(
    'proposer_privkey, proposer_pubkey, is_valid_signature',
    (
        (0, bls.privtopub(0), True),
        (0, bls.privtopub(0) + 1, False),
        (0, 123, False),

        (123, bls.privtopub(123), True),
        (123, bls.privtopub(123) + 1, False),
        (123, 123, False),
    )
)
def test_validate_proposer_signature(
        proposer_privkey,
        proposer_pubkey,
        is_valid_signature,
        sample_beacon_block_params,
        sample_beacon_state_params,
        sample_shard_committee_params,
        beacon_chain_shard_number,
        epoch_length,
        max_deposit):

    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=tuple(
            mock_validator_record(proposer_pubkey)
            for _ in range(10)
        ),
        validator_balances=tuple(
            max_deposit
            for _ in range(10)
        ),
        shard_committees_at_slots=get_sample_shard_committees_at_slots(
            num_slot=128,
            num_shard_committee_per_slot=10,
            sample_shard_committee_params=sample_shard_committee_params,
        ),
    )

    default_block = BaseBeaconBlock(**sample_beacon_block_params)
    empty_signature_block_root = default_block.block_without_signature_root

    proposal_root = ProposalSignedData(
        state.slot,
        beacon_chain_shard_number,
        empty_signature_block_root,
    ).root

    proposed_block = BaseBeaconBlock(**sample_beacon_block_params).copy(
        signature=bls.sign(
            message=proposal_root,
            privkey=proposer_privkey,
            domain=SignatureDomain.DOMAIN_PROPOSAL,
        ),
    )

    if is_valid_signature:
        validate_proposer_signature(
            state,
            proposed_block,
            beacon_chain_shard_number,
            epoch_length,
        )
    else:
        with pytest.raises(ValidationError):
            validate_proposer_signature(
                state,
                proposed_block,
                beacon_chain_shard_number,
                epoch_length,
            )
