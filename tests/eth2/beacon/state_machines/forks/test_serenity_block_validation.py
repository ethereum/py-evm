import pytest

from eth_utils import (
    ValidationError,
)

from eth2._utils import bls

from eth2.beacon.configs import (
    CommitteeConfig,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.proposal_signed_data import (
    ProposalSignedData,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.forks import Fork

from eth2.beacon.helpers import (
    get_domain,
)

from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_block_slot,
    validate_proposer_signature,
    validate_randao_reveal,
)

from tests.eth2.beacon.helpers import mock_validator_record


@pytest.mark.parametrize(
    'state_slot,'
    'block_slot,'
    'expected',
    (
        (10, 10, None),
        (1, 10, ValidationError()),
        (10, 1, ValidationError()),
    ),
)
def test_validate_block_slot(sample_beacon_state_params,
                             sample_beacon_block_params,
                             state_slot,
                             block_slot,
                             expected):
    state = BeaconState(**sample_beacon_state_params).copy(
        slot=state_slot,
    )
    block = BeaconBlock(**sample_beacon_block_params).copy(
        slot=block_slot,
    )
    if isinstance(expected, Exception):
        with pytest.raises(ValidationError):
            validate_block_slot(state, block)
    else:
        validate_block_slot(state, block)


@pytest.mark.parametrize(
    'epoch_length, shard_count,'
    'proposer_privkey, proposer_pubkey, is_valid_signature',
    (
        (5, 2, 0, bls.privtopub(0), True, ),
        (5, 2, 0, bls.privtopub(0)[1:] + b'\x01', False),
        (5, 2, 0, b'\x01\x23', False),
        (5, 2, 123, bls.privtopub(123), True),
        (5, 2, 123, bls.privtopub(123)[1:] + b'\x01', False),
        (5, 2, 123, b'\x01\x23', False),
    )
)
def test_validate_proposer_signature(
        epoch_length,
        shard_count,
        proposer_privkey,
        proposer_pubkey,
        is_valid_signature,
        sample_beacon_block_params,
        sample_beacon_state_params,
        beacon_chain_shard_number,
        genesis_epoch,
        target_committee_size,
        max_deposit_amount,
        config):

    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=tuple(
            mock_validator_record(proposer_pubkey)
            for _ in range(10)
        ),
        validator_balances=(max_deposit_amount,) * 10,
    )

    default_block = BeaconBlock(**sample_beacon_block_params)
    empty_signature_block_root = default_block.block_without_signature_root

    proposal_root = ProposalSignedData(
        state.slot,
        beacon_chain_shard_number,
        empty_signature_block_root,
    ).root

    proposed_block = BeaconBlock(**sample_beacon_block_params).copy(
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
            CommitteeConfig(config),
        )
    else:
        with pytest.raises(ValidationError):
            validate_proposer_signature(
                state,
                proposed_block,
                beacon_chain_shard_number,
                CommitteeConfig(config),
            )


@pytest.mark.parametrize(
    ["is_valid", "epoch", "expected_epoch", "proposer_key_index", "expected_proposer_key_index"],
    (
        (True, 0, 0, 0, 0),
        (True, 1, 1, 1, 1),
        (False, 0, 1, 0, 0),
        (False, 0, 0, 0, 1),
    )
)
def test_randao_reveal_validation(is_valid,
                                  epoch,
                                  expected_epoch,
                                  proposer_key_index,
                                  expected_proposer_key_index,
                                  privkeys,
                                  pubkeys,
                                  sample_fork_params,
                                  config):
    message = epoch.to_bytes(32, byteorder="big")
    slot = epoch * config.EPOCH_LENGTH
    fork = Fork(**sample_fork_params)
    domain = get_domain(fork, slot, SignatureDomain.DOMAIN_RANDAO)

    proposer_privkey = privkeys[proposer_key_index]
    randao_reveal = bls.sign(message, proposer_privkey, domain)

    expected_proposer_pubkey = pubkeys[expected_proposer_key_index]

    try:
        validate_randao_reveal(
            randao_reveal=randao_reveal,
            proposer_pubkey=expected_proposer_pubkey,
            epoch=expected_epoch,
            fork=fork,
        )
    except ValidationError:
        if is_valid:
            raise
    else:
        if not is_valid:
            pytest.fail("Did not raise")
