from typing import (
    Sequence,
    Type,
)

from eth_typing import (
    Hash32,
)

import ssz

from eth2.beacon.deposit_helpers import (
    process_deposit,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
)

from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlockBody,
)
from eth2.beacon.types.block_headers import (
    BeaconBlockHeader,
)
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import round_down_to_previous_multiple
from eth2.beacon.typing import (
    Timestamp,
    ValidatorIndex,
)
from eth2.beacon.validator_status_helpers import (
    activate_validator,
)
from eth2.configs import (
    Eth2Config,
    CommitteeConfig,
)


def is_genesis_trigger(deposits: Sequence[Deposit], timestamp: int, config: Eth2Config) -> bool:
    state = BeaconState(config=config)

    for deposit in deposits:
        state = process_deposit(state, deposit, config)

    active_validator_count = 0
    for validator in state.validators:
        if validator.effective_balance == config.MAX_EFFECTIVE_BALANCE:
            active_validator_count += 1

    return active_validator_count == config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT


def genesis_state_with_active_index_roots(state: BeaconState, config: Eth2Config) -> BeaconState:
    active_validator_indices = get_active_validator_indices(
        state.validators,
        config.GENESIS_EPOCH,
    )
    active_index_root = ssz.hash_tree_root(
        active_validator_indices,
        ssz.sedes.List(ssz.uint64),
    )
    active_index_roots = (
        (active_index_root,) * config.EPOCHS_PER_HISTORICAL_VECTOR
    )
    committee_root = get_compact_committees_root(
        state,
        config.GENESIS_EPOCH,
        CommitteeConfig(config),
    )
    compact_committees_roots = (
        (committee_root,) * config.EPOCHS_PER_HISTORICAL_VECTOR
    )
    return state.copy(
        active_index_roots=active_index_roots,
        compact_committees_roots=compact_committees_roots,
    )


def get_genesis_beacon_state(*,
                             genesis_deposits: Sequence[Deposit],
                             genesis_time: Timestamp,
                             genesis_eth1_data: Eth1Data,
                             config: Eth2Config) -> BeaconState:
    state = BeaconState(
        genesis_time=Timestamp(
            eth1_timestamp - eth1_timestamp % SECONDS_PER_DAY + 2 * SECONDS_PER_DAY,
        ),
        eth1_data=Eth1Data(
            block_hash=eth1_block_hash,
            deposit_count=len(deposits),
        ),
        latest_block_header=BeaconBlockHeader(
            body_root=BeaconBlockBody().root,
        ),
        config=config,
    )

    # Process genesis deposits
    for deposit in genesis_deposits:
        state = process_deposit(
            state=state,
            deposit=deposit,
            config=config,
        )

    # Process genesis activations
    for validator_index in range(len(state.validators)):
        validator_index = ValidatorIndex(validator_index)
        balance = state.balances[validator_index]
        effective_balance = Gwei(
            min(
                round_down_to_previous_multiple(
                    balance,
                    config.EFFECTIVE_BALANCE_INCREMENT,
                ),
                config.MAX_EFFECTIVE_BALANCE,
            )
        )

        state = state.update_validator_with_fn(
            validator_index,
            lambda v, *_: v.copy(
                effective_balance=effective_balance,
            ),
        )

        if effective_balance == config.MAX_EFFECTIVE_BALANCE:
            state = state.update_validator_with_fn(
                validator_index,
                activate_validator,
                config.GENESIS_EPOCH,
            )

    return genesis_state_with_active_index_roots(
        state,
        config,
    )


def get_genesis_block(genesis_state_root: Hash32,
                      block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
    return block_class(
        state_root=genesis_state_root,
    )
