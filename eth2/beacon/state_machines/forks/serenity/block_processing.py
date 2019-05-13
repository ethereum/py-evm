from eth_utils.toolz import (
    first,
)

from eth2._utils.hash import hash_eth2
from eth2._utils.tuple import update_tuple_item
from eth2._utils.numeric import (
    bitwise_xor,
)

from eth2.configs import (
    Eth2Config,
    CommitteeConfig,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.eth1_data_vote import Eth1DataVote

from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_randao_reveal,
)

from eth2.beacon.helpers import (
    get_randao_mix,
    get_temporary_block_header,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
)

from .block_validation import (
    validate_block_slot,
    validate_block_previous_root,
    validate_proposer_signature,
)


def process_block_header(state: BeaconState,
                         block: BaseBeaconBlock,
                         config: Eth2Config,
                         check_proposer_signature: bool) -> BeaconState:
    validate_block_slot(state, block)
    validate_block_previous_root(state, block)

    state = state.copy(
        latest_block_header=get_temporary_block_header(block),
    )

    if check_proposer_signature:
        validate_proposer_signature(
            state,
            block,
            committee_config=CommitteeConfig(config),
        )

    return state


def process_eth1_data(state: BeaconState,
                      block: BaseBeaconBlock) -> BeaconState:
    try:
        vote_index, original_vote = first(
            (index, eth1_data_vote)
            for index, eth1_data_vote in enumerate(state.eth1_data_votes)
            if block.body.eth1_data == eth1_data_vote.eth1_data
        )
    except StopIteration:
        new_vote = Eth1DataVote(
            eth1_data=block.body.eth1_data,
            vote_count=1,
        )
        state = state.copy(
            eth1_data_votes=state.eth1_data_votes + (new_vote,)
        )
    else:
        updated_vote = original_vote.copy(
            vote_count=original_vote.vote_count + 1
        )
        state = state.copy(
            eth1_data_votes=update_tuple_item(state.eth1_data_votes, vote_index, updated_vote)
        )

    return state


def process_randao(state: BeaconState,
                   block: BaseBeaconBlock,
                   config: Eth2Config) -> BeaconState:
    proposer_index = get_beacon_proposer_index(
        state=state,
        slot=state.slot,
        committee_config=CommitteeConfig(config),
    )
    proposer = state.validator_registry[proposer_index]

    epoch = state.current_epoch(config.SLOTS_PER_EPOCH)

    validate_randao_reveal(
        randao_reveal=block.body.randao_reveal,
        proposer_index=proposer_index,
        proposer_pubkey=proposer.pubkey,
        epoch=epoch,
        fork=state.fork,
    )

    randao_mix_index = epoch % config.LATEST_RANDAO_MIXES_LENGTH
    new_randao_mix = bitwise_xor(
        get_randao_mix(
            state=state,
            epoch=epoch,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
        ),
        hash_eth2(block.body.randao_reveal),
    )

    return state.copy(
        latest_randao_mixes=update_tuple_item(
            state.latest_randao_mixes,
            randao_mix_index,
            new_randao_mix,
        ),
    )
