from typing import (  # noqa: F401
    cast,
    Iterable,
    Sequence,
    Tuple,
)

from eth_typing import (
    BLSPubkey,
    BLSSignature,
    Hash32,
)
from eth_utils import (
    encode_hex,
    ValidationError,
)
import ssz

from eth.constants import (
    ZERO_HASH32,
)
from eth2._utils.hash import (
    hash_eth2,
)
from eth2._utils.bls import bls

from eth2.configs import (
    CommitteeConfig,
)
from eth2.beacon.attestation_helpers import (
    get_attestation_data_slot,
    validate_indexed_attestation,
    is_slashable_attestation_data,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
)
from eth2.beacon.epoch_processing_helpers import (
    convert_to_indexed,
)
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.signature_domain import (
    SignatureDomain,
)
from eth2.beacon.helpers import (
    get_domain,
    slot_to_epoch,
)
from eth2.beacon.types.attestations import Attestation, IndexedAttestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.blocks import BaseBeaconBlock, BeaconBlockHeader
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.transfers import Transfer
from eth2.beacon.types.voluntary_exits import VoluntaryExit
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import (
    Epoch,
    Shard,
    Slot,
)
from eth2.configs import (
    Eth2Config,
)
from eth2.beacon.exceptions import (
    SignatureError,
)


def validate_correct_number_of_deposits(state: BeaconState,
                                        block: BaseBeaconBlock,
                                        config: Eth2Config) -> None:
    body = block.body
    deposit_count_in_block = len(body.deposits)
    expected_deposit_count = min(
        config.MAX_DEPOSITS,
        state.eth1_data.deposit_count - state.eth1_deposit_index,
    )

    if deposit_count_in_block != expected_deposit_count:
        raise ValidationError(
            f"Incorrect number of deposits ({deposit_count_in_block})"
            f" in block (encode_hex(block_root));"
            f" expected {expected_deposit_count} based on the state {encode_hex(state.root)}"
        )


def validate_unique_transfers(state: BeaconState,
                              block: BaseBeaconBlock,
                              config: Eth2Config) -> None:
    body = block.body
    transfer_count_in_block = len(body.transfers)
    unique_transfer_count = len(set(body.transfers))

    if transfer_count_in_block != unique_transfer_count:
        raise ValidationError(
            f"Found duplicate transfers in the block {encode_hex(block.root)}"
        )


#
# Block validatation
#
def validate_block_slot(state: BeaconState,
                        block: BaseBeaconBlock) -> None:
    if block.slot != state.slot:
        raise ValidationError(
            f"block.slot ({block.slot}) is not equal to state.slot ({state.slot})"
        )


def validate_block_parent_root(state: BeaconState,
                               block: BaseBeaconBlock) -> None:
    expected_root = state.latest_block_header.signing_root
    parent_root = block.parent_root
    if parent_root != expected_root:
        raise ValidationError(
            f"block.parent_root ({encode_hex(parent_root)}) is not equal to "
            f"state.latest_block_header.signing_root ({encode_hex(expected_root)}"
        )


def validate_proposer_is_not_slashed(state: BeaconState,
                                     block_root: Hash32,
                                     config: CommitteeConfig) -> None:
    proposer_index = get_beacon_proposer_index(state, config)
    proposer = state.validators[proposer_index]
    if proposer.slashed:
        raise ValidationError(
            f"Proposer for block {encode_hex(block_root)} is slashed"
        )


def validate_proposer_signature(state: BeaconState,
                                block: BaseBeaconBlock,
                                committee_config: CommitteeConfig) -> None:
    message_hash = block.signing_root

    # Get the public key of proposer
    beacon_proposer_index = get_beacon_proposer_index(
        state,
        committee_config,
    )
    proposer_pubkey = state.validators[beacon_proposer_index].pubkey
    domain = get_domain(
        state,
        SignatureDomain.DOMAIN_BEACON_PROPOSER,
        committee_config.SLOTS_PER_EPOCH,
    )

    try:
        bls.validate(
            pubkey=proposer_pubkey,
            message_hash=message_hash,
            signature=block.signature,
            domain=domain,
        )
    except SignatureError as error:
        raise ValidationError(
            f"Invalid Proposer Signature on block, beacon_proposer_index={beacon_proposer_index}",
            error,
        )


#
# RANDAO validatation
#
def validate_randao_reveal(state: BeaconState,
                           proposer_index: int,
                           epoch: Epoch,
                           randao_reveal: Hash32,
                           slots_per_epoch: int) -> None:
    proposer = state.validators[proposer_index]
    proposer_pubkey = proposer.pubkey
    message_hash = ssz.hash_tree_root(epoch, sedes=ssz.sedes.uint64)
    domain = get_domain(state, SignatureDomain.DOMAIN_RANDAO, slots_per_epoch)

    try:
        bls.validate(
            pubkey=proposer_pubkey,
            message_hash=message_hash,
            signature=cast(BLSSignature, randao_reveal),
            domain=domain,
        )
    except SignatureError as error:
        raise ValidationError("RANDAO reveal is invalid", error)


#
# Proposer slashing validation
#
def validate_proposer_slashing(state: BeaconState,
                               proposer_slashing: ProposerSlashing,
                               slots_per_epoch: int) -> None:
    """
    Validate the given ``proposer_slashing``.
    Raise ``ValidationError`` if it's invalid.
    """
    proposer = state.validators[proposer_slashing.proposer_index]

    validate_proposer_slashing_epoch(proposer_slashing, slots_per_epoch)

    validate_proposer_slashing_headers(proposer_slashing)

    validate_proposer_slashing_is_slashable(state, proposer, slots_per_epoch)

    validate_block_header_signature(
        state=state,
        header=proposer_slashing.header_1,
        pubkey=proposer.pubkey,
        slots_per_epoch=slots_per_epoch,
    )

    validate_block_header_signature(
        state=state,
        header=proposer_slashing.header_2,
        pubkey=proposer.pubkey,
        slots_per_epoch=slots_per_epoch,
    )


def validate_proposer_slashing_epoch(proposer_slashing: ProposerSlashing,
                                     slots_per_epoch: int) -> None:
    epoch_1 = slot_to_epoch(proposer_slashing.header_1.slot, slots_per_epoch)
    epoch_2 = slot_to_epoch(proposer_slashing.header_2.slot, slots_per_epoch)

    if epoch_1 != epoch_2:
        raise ValidationError(
            f"Epoch of proposer_slashing.proposal_1 ({epoch_1}) !="
            f" epoch of proposer_slashing.proposal_2 ({epoch_2})"
        )


def validate_proposer_slashing_headers(proposer_slashing: ProposerSlashing) -> None:
    header_1 = proposer_slashing.header_1
    header_2 = proposer_slashing.header_2
    if header_1 == header_2:
        raise ValidationError(
            f"proposer_slashing.header_1 ({header_1}) == proposer_slashing.header_2 ({header_2})"
        )


def validate_proposer_slashing_is_slashable(state: BeaconState,
                                            proposer: Validator,
                                            slots_per_epoch: int) -> None:
    current_epoch = state.current_epoch(slots_per_epoch)
    is_slashable = proposer.is_slashable(current_epoch)
    if not is_slashable:
        raise ValidationError(
            f"Proposer {encode_hex(proposer.pubkey)} is not slashable in epoch {current_epoch}."
        )


def validate_block_header_signature(state: BeaconState,
                                    header: BeaconBlockHeader,
                                    pubkey: BLSPubkey,
                                    slots_per_epoch: int) -> None:
    try:
        bls.validate(
            pubkey=pubkey,
            message_hash=header.signing_root,
            signature=header.signature,
            domain=get_domain(
                state,
                SignatureDomain.DOMAIN_BEACON_PROPOSER,
                slots_per_epoch,
                slot_to_epoch(header.slot, slots_per_epoch),
            )
        )
    except SignatureError as error:
        raise ValidationError("Header signature is invalid", error)


#
# Attester slashing validation
#
def validate_is_slashable_attestation_data(attestation_1: IndexedAttestation,
                                           attestation_2: IndexedAttestation) -> None:
    is_slashable_data = is_slashable_attestation_data(attestation_1.data, attestation_2.data)

    if not is_slashable_data:
        raise ValidationError(
            "The `AttesterSlashing` object doesn't meet the Casper FFG slashing conditions."
        )


def validate_attester_slashing(state: BeaconState,
                               attester_slashing: AttesterSlashing,
                               max_indices_per_attestation: int,
                               slots_per_epoch: int) -> None:
    attestation_1 = attester_slashing.attestation_1
    attestation_2 = attester_slashing.attestation_2

    validate_is_slashable_attestation_data(
        attestation_1,
        attestation_2,
    )

    validate_indexed_attestation(
        state,
        attestation_1,
        max_indices_per_attestation,
        slots_per_epoch,
    )

    validate_indexed_attestation(
        state,
        attestation_2,
        max_indices_per_attestation,
        slots_per_epoch,
    )


def validate_some_slashing(slashed_any: bool, attester_slashing: AttesterSlashing) -> None:
    if not slashed_any:
        raise ValidationError(
            f"Attesting slashing {attester_slashing} did not yield any slashable validators."
        )


#
# Attestation validation
#
def _validate_eligible_shard_number(shard: Shard, shard_count: int) -> None:
    if shard >= shard_count:
        raise ValidationError(
            f"Attestation with shard {shard} must be less than the total shard count {shard_count}"
        )


def _validate_eligible_target_epoch(target_epoch: Epoch,
                                    current_epoch: Epoch,
                                    previous_epoch: Epoch) -> None:
    if target_epoch not in (previous_epoch, current_epoch):
        raise ValidationError(
            f"Attestation with target epoch {target_epoch} must be in either the"
            f" previous epoch {previous_epoch} or the current epoch {current_epoch}"
        )


def validate_attestation_slot(attestation_slot: Slot,
                              state_slot: Slot,
                              slots_per_epoch: int,
                              min_attestation_inclusion_delay: int) -> None:
    if attestation_slot + min_attestation_inclusion_delay > state_slot:
        raise ValidationError(
            f"Attestation at slot {attestation_slot} can only be included after the"
            f" minimum delay {min_attestation_inclusion_delay} with respect to the"
            f" state's slot {state_slot}."
        )

    if state_slot > attestation_slot + slots_per_epoch:
        raise ValidationError(
            f"Attestation at slot {attestation_slot} must be within {slots_per_epoch}"
            f" slots (1 epoch) of the state's slot {state_slot}"
        )


FFGData = Tuple[Epoch, Hash32, Epoch]


def _validate_ffg_data(data: AttestationData, ffg_data: FFGData) -> None:
    if ffg_data != (data.source_epoch, data.source_root, data.target_epoch):
        raise ValidationError(
            f"Attestation with data {data} did not match the expected"
            f" FFG data ({ffg_data}) based on the specified ``target_epoch``."
        )


def _validate_crosslink(crosslink: Crosslink,
                        target_epoch: Epoch,
                        parent_crosslink: Crosslink,
                        max_epochs_per_crosslink: int) -> None:
    if crosslink.start_epoch != parent_crosslink.end_epoch:
        raise ValidationError(
            f"Crosslink with start_epoch {crosslink.start_epoch} did not match the parent"
            f" crosslink's end epoch {parent_crosslink.end_epoch}."
        )

    expected_end_epoch = min(
        target_epoch,
        parent_crosslink.end_epoch + max_epochs_per_crosslink,
    )
    if crosslink.end_epoch != expected_end_epoch:
        raise ValidationError(
            f"The crosslink did not have the expected end epoch {expected_end_epoch}."
            f" The end epoch was {crosslink.end_epoch} and the expected was the minimum of"
            f" the target epoch {target_epoch} or the parent's end epoch plus the"
            f" max_epochs_per_crosslink {parent_crosslink.end_epoch + max_epochs_per_crosslink}."
        )

    if crosslink.parent_root != parent_crosslink.root:
        raise ValidationError(
            f"The parent root of the crosslink {crosslink.parent_root} did not match the root of"
            f" the expected parent's crosslink {parent_crosslink.root}."
        )

    if crosslink.data_root != ZERO_HASH32:
        raise ValidationError(
            f"The data root for this crosslink should be the zero hash."
            f" Instead it was {crosslink.data_root}"
        )


def _validate_attestation_data(state: BeaconState,
                               data: AttestationData,
                               config: Eth2Config) -> None:
    slots_per_epoch = config.SLOTS_PER_EPOCH
    current_epoch = state.current_epoch(slots_per_epoch)
    previous_epoch = state.previous_epoch(slots_per_epoch, config.GENESIS_EPOCH)

    attestation_slot = get_attestation_data_slot(state, data, config)

    if data.target_epoch == current_epoch:
        ffg_data = (
            state.current_justified_epoch,
            state.current_justified_root,
            current_epoch,
        )
        parent_crosslink = state.current_crosslinks[data.crosslink.shard]
    else:
        ffg_data = (
            state.previous_justified_epoch,
            state.previous_justified_root,
            previous_epoch,
        )
        parent_crosslink = state.previous_crosslinks[data.crosslink.shard]

    _validate_eligible_shard_number(data.crosslink.shard, config.SHARD_COUNT)
    _validate_eligible_target_epoch(data.target_epoch, current_epoch, previous_epoch)
    validate_attestation_slot(
        attestation_slot,
        state.slot,
        slots_per_epoch,
        config.MIN_ATTESTATION_INCLUSION_DELAY
    )
    _validate_ffg_data(data, ffg_data)
    _validate_crosslink(
        data.crosslink,
        data.target_epoch,
        parent_crosslink,
        config.MAX_EPOCHS_PER_CROSSLINK
    )


def validate_attestation(state: BeaconState,
                         attestation: Attestation,
                         config: Eth2Config) -> None:
    """
    Validate the given ``attestation``.
    Raise ``ValidationError`` if it's invalid.
    """
    _validate_attestation_data(state, attestation.data, config)
    validate_indexed_attestation(
        state,
        convert_to_indexed(state, attestation, CommitteeConfig(config)),
        config.MAX_INDICES_PER_ATTESTATION,
        config.SLOTS_PER_EPOCH,
    )


#
# Voluntary Exit validation
#
def _validate_validator_is_active(validator: Validator, target_epoch: Epoch) -> None:
    is_active = validator.is_active(target_epoch)
    if not is_active:
        raise ValidationError(
            f"Validator trying to exit in {target_epoch} is not active."
        )


def _validate_validator_has_not_exited(validator: Validator) -> None:
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        raise ValidationError(
            f"Validator {validator} in voluntary exit has already exited."
        )


def _validate_eligible_exit_epoch(exit_epoch: Epoch, current_epoch: Epoch) -> None:
    if current_epoch < exit_epoch:
        raise ValidationError(
            f"Validator in voluntary exit with exit epoch {exit_epoch}"
            f" is before the current epoch {current_epoch}."
        )


def _validate_validator_minimum_lifespan(validator: Validator,
                                         current_epoch: Epoch,
                                         persistent_committee_period: int) -> None:
    if current_epoch < validator.activation_epoch + persistent_committee_period:
        raise ValidationError(
            f"Validator in voluntary exit has not completed the minimum number of epochs"
            f" {persistent_committee_period} since activation in {validator.activation_epoch}"
            f" relative to the current epoch {current_epoch}."
        )


def _validate_voluntary_exit_signature(state: BeaconState,
                                       voluntary_exit: VoluntaryExit,
                                       validator: Validator,
                                       slots_per_epoch: int) -> None:
    domain = get_domain(
        state,
        SignatureDomain.DOMAIN_VOLUNTARY_EXIT,
        slots_per_epoch,
        voluntary_exit.epoch,
    )
    try:
        bls.validate(
            pubkey=validator.pubkey,
            message_hash=voluntary_exit.signing_root,
            signature=voluntary_exit.signature,
            domain=domain,
        )
    except SignatureError as error:
        raise ValidationError(
            f"Invalid VoluntaryExit signature, validator_index={voluntary_exit.validator_index}",
            error,
        )


def validate_voluntary_exit(state: BeaconState,
                            voluntary_exit: VoluntaryExit,
                            slots_per_epoch: int,
                            persistent_committee_period: int) -> None:
    validator = state.validators[voluntary_exit.validator_index]
    current_epoch = state.current_epoch(slots_per_epoch)

    _validate_validator_is_active(validator, current_epoch)
    _validate_validator_has_not_exited(validator)
    _validate_eligible_exit_epoch(voluntary_exit.epoch, current_epoch)
    _validate_validator_minimum_lifespan(
        validator,
        current_epoch,
        persistent_committee_period,
    )
    _validate_voluntary_exit_signature(state, voluntary_exit, validator, slots_per_epoch)


def _validate_amount_and_fee_magnitude(state: BeaconState, transfer: Transfer) -> None:
    threshold = state.balances[transfer.sender]
    max_amount = max(transfer.amount, transfer.fee)
    if threshold < max_amount:
        raise ValidationError(
            f"Transfer amount (transfer.amount) or fee (transfer.fee) was over the allowable"
            f" threshold {threshold}."
        )


def _validate_transfer_slot(state_slot: Slot, transfer_slot: Slot) -> None:
    if state_slot != transfer_slot:
        raise ValidationError(
            f"Transfer is only valid in the specified slot {transfer_slot} but the state is at"
            f" {state_slot}."
        )


def _validate_sender_eligibility(state: BeaconState,
                                 transfer: Transfer,
                                 config: Eth2Config) -> None:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    sender = state.validators[transfer.sender]
    sender_balance = state.balances[transfer.sender]

    eligible_for_activation = sender.activation_eligibility_epoch != FAR_FUTURE_EPOCH
    is_withdrawable = current_epoch >= sender.withdrawable_epoch
    is_transfer_total_allowed = (
        transfer.amount + transfer.fee + config.MAX_EFFECTIVE_BALANCE <= sender_balance
    )

    if not eligible_for_activation or is_withdrawable or is_transfer_total_allowed:
        return

    if eligible_for_activation:
        raise ValidationError(
            f"Sender in transfer {transfer} is eligible for activation."
        )

    if not is_withdrawable:
        raise ValidationError(
            f"Sender in transfer {transfer} is not withdrawable."
        )

    if not is_transfer_total_allowed:
        raise ValidationError(
            f"Sender does not have sufficient funds in transfer {transfer}."
        )


def _validate_sender_pubkey(state: BeaconState, transfer: Transfer, config: Eth2Config) -> None:
    sender = state.validators[transfer.sender]
    expected_withdrawal_credentials = config.BLS_WITHDRAWAL_PREFIX.to_bytes(
        1,
        byteorder='little',
    ) + hash_eth2(transfer.pubkey)[1:]
    are_withdrawal_credentials_valid = (
        sender.withdrawal_credentials == expected_withdrawal_credentials
    )

    if not are_withdrawal_credentials_valid:
        raise ValidationError(
            f"Pubkey in transfer {transfer} does not match the withdrawal credentials"
            f" {expected_withdrawal_credentials} for validator {sender}."
        )


def _validate_transfer_signature(state: BeaconState,
                                 transfer: Transfer,
                                 config: Eth2Config) -> None:
    domain = get_domain(
        state,
        SignatureDomain.DOMAIN_TRANSFER,
        config.SLOTS_PER_EPOCH,
    )
    try:
        bls.validate(
            pubkey=transfer.pubkey,
            message_hash=transfer.signing_root,
            signature=transfer.signature,
            domain=domain,
        )
    except SignatureError as error:
        raise ValidationError(
            f"Invalid signature for transfer {transfer}",
            error,
        )


def _validate_transfer_does_not_result_in_dust(state: BeaconState,
                                               transfer: Transfer,
                                               config: Eth2Config) -> None:
    resulting_sender_balance = max(
        0,
        state.balances[transfer.sender] - (transfer.amount + transfer.fee),
    )
    resulting_sender_balance_is_dust = 0 < resulting_sender_balance < config.MIN_DEPOSIT_AMOUNT
    if resulting_sender_balance_is_dust:
        raise ValidationError(
            f"Effect of transfer {transfer} results in dust balance for sender."
        )

    resulting_recipient_balance = state.balances[transfer.recipient] + transfer.amount
    resulting_recipient_balance_is_dust = (
        0 < resulting_recipient_balance < config.MIN_DEPOSIT_AMOUNT
    )
    if resulting_recipient_balance_is_dust:
        raise ValidationError(
            f"Effect of transfer {transfer} results in dust balance for recipient."
        )


def validate_transfer(state: BeaconState,
                      transfer: Transfer,
                      config: Eth2Config) -> None:
    _validate_amount_and_fee_magnitude(state, transfer)
    _validate_transfer_slot(state.slot, transfer.slot)
    _validate_sender_eligibility(state, transfer, config)
    _validate_sender_pubkey(state, transfer, config)
    _validate_transfer_signature(state, transfer, config)
    _validate_transfer_does_not_result_in_dust(state, transfer, config)
