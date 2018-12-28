from typing import (
    Sequence,
    Tuple,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    ValidationError,
)

from eth._utils import bls

from eth.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth.beacon.enums import (
    SignatureDomain,
)
from eth.beacon.exceptions import (
    MinEmptyValidatorIndexNotFound,
)
from eth.beacon.types.deposit_input import DepositInput
from eth.beacon.types.states import BeaconState
from eth.beacon.types.validator_records import ValidatorRecord
from eth.beacon.helpers import (
    get_domain,
)
from eth.beacon.typing import (
    BLSPubkey,
    BLSSignature,
    Gwei,
)


def get_min_empty_validator_index(validators: Sequence[ValidatorRecord],
                                  validator_balances: Sequence[int],
                                  current_slot: int,
                                  zero_balance_validator_ttl: int) -> int:
    for index, (validator, balance) in enumerate(zip(validators, validator_balances)):
        is_empty = (
            balance == 0 and
            validator.latest_status_change_slot + zero_balance_validator_ttl <= current_slot
        )
        if is_empty:
            return index
    raise MinEmptyValidatorIndexNotFound()


def validate_proof_of_possession(state: BeaconState,
                                 pubkey: BLSPubkey,
                                 proof_of_possession: BLSSignature,
                                 withdrawal_credentials: Hash32,
                                 randao_commitment: Hash32) -> None:
    deposit_input = DepositInput(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        proof_of_possession=EMPTY_SIGNATURE,
    )

    is_valid_signature = bls.verify(
        pubkey=pubkey,
        # TODO: change to hash_tree_root(deposit_input) when we have SSZ tree hashing
        message=deposit_input.root,
        signature=proof_of_possession,
        domain=get_domain(
            state.fork_data,
            state.slot,
            SignatureDomain.DOMAIN_DEPOSIT,
        ),
    )

    if not is_valid_signature:
        raise ValidationError(
            "BLS signature verification error"
        )


def add_pending_validator(state: BeaconState,
                          validator: ValidatorRecord,
                          deposit: Gwei,
                          zero_balance_validator_ttl: int) -> Tuple[BeaconState, int]:
    """
    Add a validator to the existing minimum empty validator index or
    append to ``validator_registry``.
    """
    # Check if there's empty validator index in `validator_registry`
    try:
        index = get_min_empty_validator_index(
            state.validator_registry,
            state.validator_balances,
            state.slot,
            zero_balance_validator_ttl,
        )
    except MinEmptyValidatorIndexNotFound:
        index = None

        # Append to the validator_registry
        validator_registry = state.validator_registry + (validator,)
        state = state.copy(
            validator_registry=validator_registry,
            validator_balances=state.validator_balances + (deposit, )
        )
        index = len(state.validator_registry) - 1
    else:
        # Use the empty validator index
        state = state.update_validator(index, validator, deposit)

    return state, index


def process_deposit(*,
                    state: BeaconState,
                    pubkey: BLSPubkey,
                    deposit: Gwei,
                    proof_of_possession: BLSSignature,
                    withdrawal_credentials: Hash32,
                    randao_commitment: Hash32,
                    zero_balance_validator_ttl: int) -> Tuple[BeaconState, int]:
    """
    Process a deposit from Ethereum 1.0.
    """
    validate_proof_of_possession(
        state,
        pubkey,
        proof_of_possession,
        withdrawal_credentials,
        randao_commitment,
    )

    validator_pubkeys = tuple(v.pubkey for v in state.validator_registry)
    if pubkey not in validator_pubkeys:
        validator = ValidatorRecord.get_pending_validator(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            latest_status_change_slot=state.slot,
        )

        state, index = add_pending_validator(
            state,
            validator,
            deposit,
            zero_balance_validator_ttl,
        )
    else:
        # Top-up - increase balance by deposit
        index = validator_pubkeys.index(pubkey)
        validator = state.validator_registry[index]

        if validator.withdrawal_credentials != withdrawal_credentials:
            raise ValidationError(
                "`withdrawal_credentials` are incorrect:\n"
                "\texpected: %s, found: %s" % (
                    validator.withdrawal_credentials,
                    validator.withdrawal_credentials,
                )
            )

        # Update validator's balance and state
        state = state.update_validator(
            validator_index=index,
            validator=validator,
            balance=state.validator_balances[index] + deposit,
        )

    return state, index
