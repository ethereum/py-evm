import pytest

from eth.constants import (
    ZERO_HASH32,
)
from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import (
    first,
)

from eth2._utils import bls

from eth2.beacon.types.forks import Fork
from eth2.beacon.types.eth1_data_vote import Eth1DataVote
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.enums import SignatureDomain

from eth2.beacon.helpers import (
    get_domain,
    get_epoch_start_slot,
)

from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.state_machines.forks.serenity.states import (
    SerenityBeaconState,
)

from eth2.beacon.state_machines.forks.serenity.block_processing import (
    process_eth1_data,
    process_randao,
)
from eth2.beacon.tools.builder.proposer import (
    _generate_randao_reveal,
)

from tests.eth2.beacon.helpers import (
    mock_validator_record,
)


def test_randao_processing(sample_beacon_block_params,
                           sample_beacon_state_params,
                           keymap,
                           config):
    proposer_pubkey, proposer_privkey = first(keymap.items())
    state = SerenityBeaconState(**sample_beacon_state_params).copy(
        validator_registry=tuple(
            mock_validator_record(proposer_pubkey, config)
            for _ in range(config.TARGET_COMMITTEE_SIZE)
        ),
        validator_balances=(config.MAX_DEPOSIT_AMOUNT,) * config.TARGET_COMMITTEE_SIZE,

        latest_randao_mixes=tuple(
            ZERO_HASH32
            for _ in range(config.LATEST_RANDAO_MIXES_LENGTH)
        ),
    )

    epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    slot = get_epoch_start_slot(epoch, config.SLOTS_PER_EPOCH)

    randao_reveal = _generate_randao_reveal(
        privkey=proposer_privkey,
        slot=slot,
        fork=state.fork,
        config=config,
    )

    block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
        randao_reveal=randao_reveal,
    )

    new_state = process_randao(state, block, config)

    updated_index = epoch % config.LATEST_RANDAO_MIXES_LENGTH
    original_mixes = state.latest_randao_mixes
    updated_mixes = new_state.latest_randao_mixes

    assert all(
        updated == original if index != updated_index else updated != original
        for index, (updated, original) in enumerate(zip(updated_mixes, original_mixes))
    )


def test_randao_processing_validates_randao_reveal(sample_beacon_block_params,
                                                   sample_beacon_state_params,
                                                   sample_fork_params,
                                                   keymap,
                                                   config):
    proposer_pubkey, proposer_privkey = first(keymap.items())
    state = SerenityBeaconState(**sample_beacon_state_params).copy(
        validator_registry=tuple(
            mock_validator_record(proposer_pubkey, config)
            for _ in range(config.TARGET_COMMITTEE_SIZE)
        ),
        validator_balances=(config.MAX_DEPOSIT_AMOUNT,) * config.TARGET_COMMITTEE_SIZE,

        latest_randao_mixes=tuple(
            ZERO_HASH32
            for _ in range(config.LATEST_RANDAO_MIXES_LENGTH)
        ),
    )

    epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    slot = epoch * config.SLOTS_PER_EPOCH
    message_hash = (epoch + 1).to_bytes(32, byteorder="little")
    fork = Fork(**sample_fork_params)
    domain = get_domain(fork, slot, SignatureDomain.DOMAIN_RANDAO)
    randao_reveal = bls.sign(message_hash, proposer_privkey, domain)

    block = SerenityBeaconBlock(**sample_beacon_block_params).copy(
        randao_reveal=randao_reveal,
    )

    with pytest.raises(ValidationError):
        process_randao(state, block, config)


HASH1 = b"\x11" * 32
HASH2 = b"\x22" * 32


@pytest.mark.parametrize(("original_votes", "block_data", "expected_votes"), (
    ((), HASH1, ((HASH1, 1),)),
    (((HASH1, 5),), HASH1, ((HASH1, 6),)),
    (((HASH2, 5),), HASH1, ((HASH2, 5), (HASH1, 1))),
    (((HASH1, 10), (HASH2, 2)), HASH2, ((HASH1, 10), (HASH2, 3))),
))
def test_process_eth1_data(original_votes,
                           block_data,
                           expected_votes,
                           sample_beacon_state_params,
                           sample_beacon_block_params):
    eth1_data_votes = tuple(
        Eth1DataVote(data, vote_count)
        for data, vote_count in original_votes
    )
    state = BeaconState(**sample_beacon_state_params).copy(
        eth1_data_votes=eth1_data_votes,
    )

    block = BeaconBlock(**sample_beacon_block_params).copy(
        eth1_data=block_data,
    )

    updated_state = process_eth1_data(state, block)
    updated_votes = tuple(
        (vote.eth1_data, vote.vote_count)
        for vote in updated_state.eth1_data_votes
    )
    assert updated_votes == expected_votes
