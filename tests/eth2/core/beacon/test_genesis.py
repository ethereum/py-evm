import pytest

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody
from eth2.beacon.types.block_headers import BeaconBlockHeader
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.forks import Fork
from eth2.beacon.genesis import (
    get_genesis_block,
    get_genesis_beacon_state,
)
from eth2.beacon.tools.builder.initializer import (
    create_mock_deposits_and_root,
)
from eth2.beacon.typing import (
    Gwei,
)


def test_get_genesis_block():
    genesis_state_root = b'\x10' * 32
    genesis_slot = 0
    genesis_block = get_genesis_block(genesis_state_root, BeaconBlock)
    assert genesis_block.slot == genesis_slot
    assert genesis_block.parent_root == ZERO_HASH32
    assert genesis_block.state_root == genesis_state_root
    assert genesis_block.signature == EMPTY_SIGNATURE
    assert genesis_block.body.is_empty


@pytest.mark.parametrize(
    (
        'validator_count,'
    ),
    [
        (10)
    ]
)
def test_get_genesis_beacon_state(
        validator_count,
        pubkeys,
        genesis_epoch,
        genesis_slot,
        shard_count,
        slots_per_historical_root,
        epochs_per_slashed_balances_vector,
        epochs_per_historical_vector,
        config,
        keymap):
    genesis_deposits, deposit_root = create_mock_deposits_and_root(
        pubkeys=pubkeys[:validator_count],
        keymap=keymap,
        config=config,
    )

    genesis_eth1_data = Eth1Data(
        deposit_count=len(genesis_deposits),
        deposit_root=deposit_root,
        block_hash=ZERO_HASH32,
    )
    genesis_time = 10

    state = get_genesis_beacon_state(
        genesis_deposits=genesis_deposits,
        genesis_time=genesis_time,
        genesis_eth1_data=genesis_eth1_data,
        config=config,
    )

    # Versioning
    assert state.slot == genesis_slot
    assert state.genesis_time == genesis_time
    assert state.fork == Fork()

    # History
    assert state.latest_block_header == BeaconBlockHeader(
        body_root=BeaconBlockBody().root,
    )
    assert len(state.block_roots) == slots_per_historical_root
    assert state.block_roots == (ZERO_HASH32,) * slots_per_historical_root
    assert len(state.state_roots) == slots_per_historical_root
    assert state.block_roots == (ZERO_HASH32,) * slots_per_historical_root
    assert len(state.historical_roots) == 0

    # Ethereum 1.0 chain data
    assert state.eth1_data == genesis_eth1_data
    assert len(state.eth1_data_votes) == 0
    assert state.eth1_deposit_index == len(genesis_deposits)

    # Validator registry
    assert len(state.validators) == validator_count
    assert len(state.balances) == validator_count

    # Shuffling
    assert state.start_shard == 0
    assert len(state.randao_mixes) == epochs_per_historical_vector
    assert state.randao_mixes == (ZERO_HASH32,) * epochs_per_historical_vector
    assert len(state.active_index_roots) == epochs_per_historical_vector

    # Slashings
    assert len(state.slashed_balances) == epochs_per_slashed_balances_vector
    assert state.slashed_balances == (Gwei(0),) * epochs_per_slashed_balances_vector

    # Attestations
    assert len(state.previous_epoch_attestations) == 0
    assert len(state.current_epoch_attestations) == 0

    # Crosslinks
    assert len(state.current_crosslinks) == shard_count
    assert state.current_crosslinks == (Crosslink(),) * shard_count
    assert len(state.previous_crosslinks) == shard_count
    assert state.previous_crosslinks == (Crosslink(),) * shard_count

    # Justification
    assert state.previous_justified_epoch == genesis_epoch
    assert state.previous_justified_root == ZERO_HASH32
    assert state.current_justified_epoch == genesis_epoch
    assert state.current_justified_root == ZERO_HASH32
    assert state.justification_bitfield == 0

    # Finalization
    assert state.finalized_epoch == genesis_epoch
    assert state.finalized_root == ZERO_HASH32

    for i in range(len(genesis_deposits)):
        assert state.validators[i].is_active(genesis_epoch)
