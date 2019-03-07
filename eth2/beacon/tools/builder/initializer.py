from typing import (
    Dict,
    Sequence,
    Tuple,
    Type,
)

from eth_typing import (
    BLSPubkey,
    Hash32,
)

from eth2.beacon.configs import BeaconConfig
from eth2.beacon.on_genesis import (
    get_genesis_block,
    get_genesis_beacon_state,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.deposit_input import DepositInput
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Timestamp,
)

from eth2.beacon.tools.builder.validator import (
    sign_proof_of_possession,
)


def create_mock_genesis_validator_deposits(
        num_validators: int,
        config: BeaconConfig,
        pubkeys: Sequence[BLSPubkey],
        keymap: Dict[BLSPubkey, int]) -> Tuple[Deposit, ...]:
    # Mock data
    withdrawal_credentials = Hash32(b'\x22' * 32)
    deposit_timestamp = Timestamp(0)
    fork = Fork(
        previous_version=config.GENESIS_FORK_VERSION,
        current_version=config.GENESIS_FORK_VERSION,
        epoch=config.GENESIS_EPOCH,
    )

    genesis_validator_deposits = tuple(
        Deposit(
            branch=tuple(
                Hash32(b'\x11' * 32)
                for j in range(10)
            ),
            index=i,
            deposit_data=DepositData(
                deposit_input=DepositInput(
                    pubkey=pubkeys[i],
                    withdrawal_credentials=withdrawal_credentials,
                    proof_of_possession=sign_proof_of_possession(
                        deposit_input=DepositInput(
                            pubkey=pubkeys[i],
                            withdrawal_credentials=withdrawal_credentials,
                        ),
                        privkey=keymap[pubkeys[i]],
                        fork=fork,
                        slot=config.GENESIS_SLOT,
                        slots_per_epoch=config.SLOTS_PER_EPOCH,
                    ),
                ),
                amount=config.MAX_DEPOSIT_AMOUNT,
                timestamp=deposit_timestamp,
            ),
        )
        for i in range(num_validators)
    )

    return genesis_validator_deposits


ZERO_TIMESTAMP = Timestamp(0)


def create_mock_genesis(
        num_validators: int,
        config: BeaconConfig,
        keymap: Dict[BLSPubkey, int],
        genesis_block_class: Type[BaseBeaconBlock],
        genesis_time: Timestamp=ZERO_TIMESTAMP) -> Tuple[BeaconState, BaseBeaconBlock]:
    latest_eth1_data = Eth1Data.create_empty_data()

    assert num_validators <= len(keymap)

    pubkeys = list(keymap)[:num_validators]

    genesis_validator_deposits = create_mock_genesis_validator_deposits(
        num_validators=num_validators,
        config=config,
        pubkeys=pubkeys,
        keymap=keymap,
    )
    state = get_genesis_beacon_state(
        genesis_validator_deposits=genesis_validator_deposits,
        genesis_time=genesis_time,
        latest_eth1_data=latest_eth1_data,
        genesis_slot=config.GENESIS_SLOT,
        genesis_epoch=config.GENESIS_EPOCH,
        genesis_fork_version=config.GENESIS_FORK_VERSION,
        genesis_start_shard=config.GENESIS_START_SHARD,
        shard_count=config.SHARD_COUNT,
        min_seed_lookahead=config.MIN_SEED_LOOKAHEAD,
        latest_block_roots_length=config.LATEST_BLOCK_ROOTS_LENGTH,
        latest_active_index_roots_length=config.LATEST_ACTIVE_INDEX_ROOTS_LENGTH,
        slots_per_epoch=config.SLOTS_PER_EPOCH,
        max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
        latest_slashed_exit_length=config.LATEST_SLASHED_EXIT_LENGTH,
        latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
        activation_exit_delay=config.ACTIVATION_EXIT_DELAY,
    )

    block = get_genesis_block(
        genesis_state_root=state.root,
        genesis_slot=config.GENESIS_SLOT,
        block_class=genesis_block_class,
    )
    assert len(state.validator_registry) == num_validators

    return state, block
