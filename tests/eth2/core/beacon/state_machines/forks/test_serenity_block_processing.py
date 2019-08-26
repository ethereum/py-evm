from eth.constants import ZERO_HASH32
from eth_utils import ValidationError
from eth_utils.toolz import concat, first, mapcat
import pytest

from eth2._utils.bls import bls
from eth2.beacon.helpers import compute_start_slot_of_epoch, get_domain
from eth2.beacon.signature_domain import SignatureDomain
from eth2.beacon.state_machines.forks.serenity.block_processing import (
    process_eth1_data,
    process_randao,
)
from eth2.beacon.state_machines.forks.serenity.blocks import SerenityBeaconBlock
from eth2.beacon.state_machines.forks.serenity.states import SerenityBeaconState
from eth2.beacon.tools.builder.initializer import create_mock_validator
from eth2.beacon.tools.builder.proposer import _generate_randao_reveal
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.states import BeaconState


def test_randao_processing(
    sample_beacon_block_params,
    sample_beacon_block_body_params,
    sample_beacon_state_params,
    keymap,
    config,
):
    proposer_pubkey, proposer_privkey = first(keymap.items())
    state = SerenityBeaconState(**sample_beacon_state_params).copy(
        validators=tuple(
            create_mock_validator(proposer_pubkey, config)
            for _ in range(config.TARGET_COMMITTEE_SIZE)
        ),
        balances=(config.MAX_EFFECTIVE_BALANCE,) * config.TARGET_COMMITTEE_SIZE,
        randao_mixes=tuple(
            ZERO_HASH32 for _ in range(config.EPOCHS_PER_HISTORICAL_VECTOR)
        ),
    )

    epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    slot = compute_start_slot_of_epoch(epoch, config.SLOTS_PER_EPOCH)

    randao_reveal = _generate_randao_reveal(
        privkey=proposer_privkey, slot=slot, state=state, config=config
    )

    block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
        randao_reveal=randao_reveal
    )

    block = SerenityBeaconBlock(**sample_beacon_block_params).copy(body=block_body)

    new_state = process_randao(state, block, config)

    updated_index = epoch % config.EPOCHS_PER_HISTORICAL_VECTOR
    original_mixes = state.randao_mixes
    updated_mixes = new_state.randao_mixes

    assert all(
        updated == original if index != updated_index else updated != original
        for index, (updated, original) in enumerate(zip(updated_mixes, original_mixes))
    )


def test_randao_processing_validates_randao_reveal(
    sample_beacon_block_params,
    sample_beacon_block_body_params,
    sample_beacon_state_params,
    sample_fork_params,
    keymap,
    config,
):
    proposer_pubkey, proposer_privkey = first(keymap.items())
    state = SerenityBeaconState(**sample_beacon_state_params).copy(
        validators=tuple(
            create_mock_validator(proposer_pubkey, config)
            for _ in range(config.TARGET_COMMITTEE_SIZE)
        ),
        balances=(config.MAX_EFFECTIVE_BALANCE,) * config.TARGET_COMMITTEE_SIZE,
        randao_mixes=tuple(
            ZERO_HASH32 for _ in range(config.EPOCHS_PER_HISTORICAL_VECTOR)
        ),
    )

    epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    message_hash = (epoch + 1).to_bytes(32, byteorder="little")
    domain = get_domain(state, SignatureDomain.DOMAIN_RANDAO, config.SLOTS_PER_EPOCH)
    randao_reveal = bls.sign(message_hash, proposer_privkey, domain)

    block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
        randao_reveal=randao_reveal
    )

    block = SerenityBeaconBlock(**sample_beacon_block_params).copy(body=block_body)

    with pytest.raises(ValidationError):
        process_randao(state, block, config)


HASH1 = b"\x11" * 32
HASH2 = b"\x22" * 32


def _expand_eth1_votes(args):
    block_hash, vote_count = args
    return (Eth1Data(block_hash=block_hash),) * vote_count


@pytest.mark.parametrize(
    ("original_votes", "block_data", "expected_votes"),
    (
        ((), HASH1, ((HASH1, 1),)),
        (((HASH1, 5),), HASH1, ((HASH1, 6),)),
        (((HASH2, 5),), HASH1, ((HASH2, 5), (HASH1, 1))),
        (((HASH1, 10), (HASH2, 2)), HASH2, ((HASH1, 10), (HASH2, 3))),
    ),
)
def test_process_eth1_data(
    original_votes,
    block_data,
    expected_votes,
    sample_beacon_state_params,
    sample_beacon_block_params,
    sample_beacon_block_body_params,
    config,
):
    eth1_data_votes = tuple(mapcat(_expand_eth1_votes, original_votes))
    state = BeaconState(**sample_beacon_state_params).copy(
        eth1_data_votes=eth1_data_votes
    )

    block_body = BeaconBlockBody(**sample_beacon_block_body_params).copy(
        eth1_data=Eth1Data(block_hash=block_data)
    )

    block = BeaconBlock(**sample_beacon_block_params).copy(body=block_body)

    updated_state = process_eth1_data(state, block, config)
    updated_votes = updated_state.eth1_data_votes
    expanded_expected_votes = tuple(mapcat(_expand_eth1_votes, expected_votes))

    assert updated_votes == expanded_expected_votes


@pytest.mark.parametrize(("slots_per_eth1_voting_period"), ((16),))
@pytest.mark.parametrize(
    ("vote_offsets"),  # a tuple of offsets against the majority threshold
    (
        # no eth1_data_votes
        (),
        # a minority of eth1_data_votes (single)
        (-2,),
        # a plurality of eth1_data_votes (multiple but not majority)
        (-2, -2),
        # almost a majority!
        (0,),
        # a majority of eth1_data_votes
        (1,),
        (7,),
        (12,),
        # NOTE: we are accepting more than one block per slot if
        # there are multiple majorities so no need to test this
    ),
)
def test_ensure_update_eth1_vote_if_exists(genesis_state, config, vote_offsets):
    # one less than a majority is the majority divided by 2
    threshold = config.SLOTS_PER_ETH1_VOTING_PERIOD // 2
    data_votes = tuple(
        concat(
            (Eth1Data(block_hash=(i).to_bytes(32, "little")),) * (threshold + offset)
            for i, offset in enumerate(vote_offsets)
        )
    )
    state = genesis_state

    for vote in data_votes:
        state = process_eth1_data(
            state, BeaconBlock(body=BeaconBlockBody(eth1_data=vote)), config
        )

    if not vote_offsets:
        assert state.eth1_data == genesis_state.eth1_data

    # we should update the 'latest' entry if we have a majority
    for offset in vote_offsets:
        if offset <= 0:
            assert genesis_state.eth1_data == state.eth1_data
        else:
            assert state.eth1_data == data_votes[0]
