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

from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth2.beacon.deposit_helpers import (
    process_deposit,
)
from eth2.beacon.helpers import (
    get_effective_balance,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
    BeaconBlockBody,
)
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.fork_data import ForkData
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Bitfield,
    Ether,
    Gwei,
    SlotNumber,
    Timestamp,
    ValidatorIndex,
)
from eth2.beacon.validator_status_helpers import (
    activate_validator,
)


def get_genesis_block(startup_state_root: Hash32, genesis_slot: SlotNumber) -> BaseBeaconBlock:
    return BeaconBlock(
        slot=genesis_slot,
        parent_root=ZERO_HASH32,
        state_root=startup_state_root,
        randao_reveal=ZERO_HASH32,
        candidate_pow_receipt_root=ZERO_HASH32,
        signature=EMPTY_SIGNATURE,
        body=BeaconBlockBody.create_empty_body(),
    )


def get_initial_beacon_state(*,
                             initial_validator_deposits: Sequence[Deposit],
                             genesis_time: Timestamp,
                             processed_pow_receipt_root: Hash32,
                             genesis_slot: SlotNumber,
                             genesis_fork_version: int,
                             shard_count: int,
                             latest_block_roots_length: int,
                             epoch_length: int,
                             target_committee_size: int,
                             max_deposit: Ether,
                             latest_penalized_exit_length: int,
                             latest_randao_mixes_length: int,
                             entry_exit_delay: int) -> BeaconState:
    state = BeaconState(
        # Misc
        slot=genesis_slot,
        genesis_time=genesis_time,
        fork_data=ForkData(
            pre_fork_version=genesis_fork_version,
            post_fork_version=genesis_fork_version,
            fork_slot=genesis_slot,
        ),

        # Validator registry
        validator_registry=(),
        validator_balances=(),
        validator_registry_latest_change_slot=genesis_slot,
        validator_registry_exit_count=0,
        validator_registry_delta_chain_tip=ZERO_HASH32,

        # Randomness and committees
        latest_randao_mixes=tuple(ZERO_HASH32 for _ in range(latest_randao_mixes_length)),
        latest_vdf_outputs=tuple(
            ZERO_HASH32 for _ in range(latest_randao_mixes_length // epoch_length)
        ),
        shard_committees_at_slots=(),
        persistent_committees=(),
        persistent_committee_reassignments=(),
        # TODO: add `previous_epoch_start_shard`, `current_epoch_start_shard`
        # `previous_epoch_calculation_slot`, `current_epoch_calculation_slot`
        # `previous_epoch_randao_mix`, `current_epoch_randao_mix`

        # Finality
        previous_justified_slot=genesis_slot,
        justified_slot=genesis_slot,
        justification_bitfield=Bitfield(b'\x00'),
        finalized_slot=genesis_slot,

        # Recent state
        latest_crosslinks=tuple([
            CrosslinkRecord(slot=genesis_slot, shard_block_root=ZERO_HASH32)
            for _ in range(shard_count)
        ]),
        latest_block_roots=tuple(ZERO_HASH32 for _ in range(latest_block_roots_length)),
        latest_penalized_exit_balances=tuple(
            Gwei(0)
            for _ in range(latest_penalized_exit_length)
        ),
        latest_attestations=(),
        batched_block_roots=(),

        # PoW receipt root
        # TODO: either (i) `processed_pow_receipt_root` => `latest_deposit_root`,
        # `candidate_pow_receipt_roots` => `deposit_root_votes` or (ii) change to
        # use PoW chain block root
        processed_pow_receipt_root=processed_pow_receipt_root,
        candidate_pow_receipt_roots=(),
    )

    # Process initial deposits
    for deposit in initial_validator_deposits:
        state = process_deposit(
            state=state,
            pubkey=deposit.deposit_data.deposit_input.pubkey,
            amount=deposit.deposit_data.amount,
            proof_of_possession=deposit.deposit_data.deposit_input.proof_of_possession,
            withdrawal_credentials=deposit.deposit_data.deposit_input.withdrawal_credentials,
            randao_commitment=deposit.deposit_data.deposit_input.randao_commitment,
            custody_commitment=deposit.deposit_data.deposit_input.custody_commitment,
        )

    for validator_index, _ in enumerate(state.validator_registry):
        validator_index = ValidatorIndex(validator_index)
        is_enough_effective_balance = get_effective_balance(
            state.validator_balances,
            validator_index,
            max_deposit,
        ) >= max_deposit * denoms.gwei
        if is_enough_effective_balance:
            state = activate_validator(
                state,
                validator_index,
                genesis=True,
                genesis_slot=genesis_slot,
                entry_exit_delay=entry_exit_delay,
            )

    return state
