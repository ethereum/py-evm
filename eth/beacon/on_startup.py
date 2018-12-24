from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    denoms,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth.beacon.enums import (
    ValidatorStatusCode,
)
from eth.beacon.deposit_helpers import (
    process_deposit,
)
from eth.beacon.helpers import (
    get_active_validator_indices,
    get_effective_balance,
    get_new_shuffling,
)
from eth.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlockBody,
)
from eth.beacon.types.crosslink_records import CrosslinkRecord
from eth.beacon.types.deposits import Deposit
from eth.beacon.types.fork_data import ForkData
from eth.beacon.types.states import BeaconState
from eth.beacon._utils.random import (
    shuffle,
    split,
)
from eth.beacon.validator_status_helpers import (
    update_validator_status,
)


def get_genesis_block(startup_state_root: Hash32, initial_slot_number: int) -> BaseBeaconBlock:
    return BaseBeaconBlock(
        slot=initial_slot_number,
        parent_root=ZERO_HASH32,
        state_root=startup_state_root,
        randao_reveal=ZERO_HASH32,
        candidate_pow_receipt_root=ZERO_HASH32,
        signature=EMPTY_SIGNATURE,
        body=BeaconBlockBody(
            proposer_slashings=(),
            casper_slashings=(),
            attestations=(),
            deposits=(),
            exits=(),
        ),
    )


def get_initial_beacon_state(*,
                             initial_validator_deposits: Sequence[Deposit],
                             genesis_time: int,
                             processed_pow_receipt_root: Hash32,
                             initial_slot_number: int,
                             initial_fork_version: int,
                             shard_count: int,
                             latest_block_roots_length: int,
                             epoch_length: int,
                             target_committee_size: int,
                             max_deposit: int,
                             zero_balance_validator_ttl: int,
                             collective_penalty_calculation_period: int,
                             whistleblower_reward_quotient: int) -> BeaconState:
    state = BeaconState(
        # Misc
        slot=initial_slot_number,
        genesis_time=genesis_time,
        fork_data=ForkData(
            pre_fork_version=initial_fork_version,
            post_fork_version=initial_fork_version,
            fork_slot=initial_slot_number,
        ),

        # Validator registry
        validator_registry=(),
        validator_registry_latest_change_slot=initial_slot_number,
        validator_registry_exit_count=0,
        validator_registry_delta_chain_tip=ZERO_HASH32,

        # Randomness and committees
        randao_mix=ZERO_HASH32,
        next_seed=ZERO_HASH32,
        shard_committees_at_slots=(),
        persistent_committees=(),
        persistent_committee_reassignments=(),

        # Finality
        previous_justified_slot=initial_slot_number,
        justified_slot=initial_slot_number,
        justification_bitfield=0,
        finalized_slot=initial_slot_number,

        # Recent state
        latest_crosslinks=tuple([
            CrosslinkRecord(slot=initial_slot_number, shard_block_root=ZERO_HASH32)
            for _ in range(shard_count)
        ]),
        latest_block_roots=tuple([ZERO_HASH32 for _ in range(latest_block_roots_length)]),
        latest_penalized_exit_balances=(),
        latest_attestations=(),
        batched_block_roots=(),

        # PoW receipt root
        processed_pow_receipt_root=processed_pow_receipt_root,
        candidate_pow_receipt_roots=(),
    )

    # handle initial deposits and activations
    for deposit in initial_validator_deposits:
        state, validator_index = process_deposit(
            state=state,
            pubkey=deposit.deposit_data.deposit_input.pubkey,
            deposit=deposit.deposit_data.value,
            proof_of_possession=deposit.deposit_data.deposit_input.proof_of_possession,
            withdrawal_credentials=deposit.deposit_data.deposit_input.withdrawal_credentials,
            randao_commitment=deposit.deposit_data.deposit_input.randao_commitment,
            zero_balance_validator_ttl=zero_balance_validator_ttl,
        )
        # TODO: BeaconState.validator_balances
        is_max_deposit = get_effective_balance(
            state.validator_registry[validator_index],
            max_deposit,
        ) == max_deposit * denoms.gwei
        if is_max_deposit:
            state = update_validator_status(
                state=state,
                index=validator_index,
                new_status=ValidatorStatusCode.ACTIVE,
                collective_penalty_calculation_period=collective_penalty_calculation_period,
                whistleblower_reward_quotient=whistleblower_reward_quotient,
                epoch_length=epoch_length,
                max_deposit=max_deposit,
            )

    # set initial committee shuffling
    initial_shuffling = get_new_shuffling(
        seed=ZERO_HASH32,
        validators=state.validator_registry,
        crosslinking_start_shard=0,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    shard_committees_at_slots = initial_shuffling + initial_shuffling
    state = state.copy(
        shard_committees_at_slots=shard_committees_at_slots,
    )

    # set initial persistent shuffling
    active_validator_indices = get_active_validator_indices(state.validator_registry)
    persistent_committees = split(shuffle(active_validator_indices, ZERO_HASH32), shard_count)
    state = state.copy(
        persistent_committees=persistent_committees,
    )

    return state
