import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_proposer_slashing,
    validate_proposer_slashing_block_root,
    validate_proposer_slashing_slashed_epoch,
    validate_proposer_slashing_slot,
    validate_proposer_slashing_shard,
    validate_proposal_signature,
)
from eth2.beacon.tools.builder.validator import (
    create_mock_proposer_slashing_at_block,
)


def get_valid_proposer_slashing(state,
                                keymap,
                                config,
                                proposer_index=0):
    return create_mock_proposer_slashing_at_block(
        state,
        config,
        keymap,
        block_root_1=b'\x11' * 32,
        block_root_2=b'\x22' * 32,
        proposer_index=proposer_index,
    )


def test_validate_proposer_slashing_valid(genesis_state,
                                          keymap,
                                          epoch_length,
                                          config):
    state = genesis_state
    valid_proposer_slashing = get_valid_proposer_slashing(
        state,
        keymap,
        config,
    )
    validate_proposer_slashing(state, valid_proposer_slashing, epoch_length)


def test_validate_proposer_slashing_slot(genesis_state,
                                         keymap,
                                         config):
    state = genesis_state
    valid_proposer_slashing = get_valid_proposer_slashing(
        state,
        keymap,
        config,
    )
    # Valid
    validate_proposer_slashing_slot(valid_proposer_slashing)

    proposal_data_1 = valid_proposer_slashing.proposal_data_1.copy(
        slot=valid_proposer_slashing.proposal_data_2.slot + 1
    )
    invalid_proposer_slashing = valid_proposer_slashing.copy(
        proposal_data_1=proposal_data_1,
    )

    # Invalid
    with pytest.raises(ValidationError):
        validate_proposer_slashing_slot(invalid_proposer_slashing)


def test_validate_proposer_slashing_shard(genesis_state,
                                          keymap,
                                          config):
    state = genesis_state
    valid_proposer_slashing = get_valid_proposer_slashing(
        state,
        keymap,
        config,
    )

    # Valid
    validate_proposer_slashing_shard(valid_proposer_slashing)

    proposal_data_1 = valid_proposer_slashing.proposal_data_1.copy(
        shard=valid_proposer_slashing.proposal_data_2.shard + 1
    )
    invalid_proposer_slashing = valid_proposer_slashing.copy(
        proposal_data_1=proposal_data_1,
    )

    # Invalid
    with pytest.raises(ValidationError):
        validate_proposer_slashing_shard(invalid_proposer_slashing)


def test_validate_proposer_slashing_block_root(genesis_state,
                                               keymap,
                                               config):
    state = genesis_state
    valid_proposer_slashing = get_valid_proposer_slashing(
        state,
        keymap,
        config,
    )

    # Valid
    validate_proposer_slashing_block_root(valid_proposer_slashing)

    proposal_data_1 = valid_proposer_slashing.proposal_data_1.copy(
        block_root=valid_proposer_slashing.proposal_data_2.block_root
    )
    invalid_proposer_slashing = valid_proposer_slashing.copy(
        proposal_data_1=proposal_data_1,
    )

    # Invalid
    with pytest.raises(ValidationError):
        validate_proposer_slashing_block_root(invalid_proposer_slashing)


@pytest.mark.parametrize(
    (
        'proposer_slashed_epoch', 'state_current_epoch', 'success'
    ),
    [
        (2, 1, True),
        (1, 1, False),
        (1, 2, False),
    ],
)
def test_validate_proposer_slashing_slashed_epoch(epoch_length,
                                                  genesis_state,
                                                  beacon_chain_shard_number,
                                                  keymap,
                                                  proposer_slashed_epoch,
                                                  state_current_epoch,
                                                  success):
    # Invalid
    if success:
        validate_proposer_slashing_slashed_epoch(proposer_slashed_epoch, state_current_epoch)
    else:
        with pytest.raises(ValidationError):
            validate_proposer_slashing_slashed_epoch(proposer_slashed_epoch, state_current_epoch)


def test_validate_proposal_signature(epoch_length,
                                     genesis_state,
                                     keymap,
                                     config):
    state = genesis_state
    proposer_index = 0
    valid_proposer_slashing = get_valid_proposer_slashing(
        state,
        keymap,
        config,
    )
    proposer = state.validator_registry[proposer_index]

    # Valid
    validate_proposal_signature(
        proposal_signed_data=valid_proposer_slashing.proposal_data_1,
        proposal_signature=valid_proposer_slashing.proposal_signature_1,
        pubkey=proposer.pubkey,
        fork=state.fork,
        epoch_length=epoch_length,
    )

    # Invalid
    wrong_proposer_index = proposer_index + 1
    wrong_proposer = state.validator_registry[wrong_proposer_index]
    with pytest.raises(ValidationError):
        validate_proposal_signature(
            proposal_signed_data=valid_proposer_slashing.proposal_data_1,
            proposal_signature=valid_proposer_slashing.proposal_signature_1,
            pubkey=wrong_proposer.pubkey,
            fork=state.fork,
            epoch_length=epoch_length,
        )
