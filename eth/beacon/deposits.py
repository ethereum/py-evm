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

from eth.utils import bls

from eth.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth.beacon.enums import (
    SignatureDomain,
    ValidatorStatusCode,
)
from eth.beacon.types.deposit_input import DepositInput
from eth.beacon.types.states import BeaconState
from eth.beacon.types.validator_records import ValidatorRecord
from eth.beacon.helpers import (
    get_domain,
)


def min_empty_validator_index(validators: Sequence[ValidatorRecord],
                              current_slot: int,
                              zero_balance_validator_ttl: int) -> int:
    for index, validator in enumerate(validators):
        if (
                validator.balance == 0 and
                validator.latest_status_change_slot + zero_balance_validator_ttl <=
                current_slot
        ):
            return index
    return None


def validate_proof_of_possession(state: BeaconState,
                                 pubkey: int,
                                 proof_of_possession: bytes,
                                 withdrawal_credentials: Hash32,
                                 randao_commitment: Hash32) -> bool:
    deposit_input = DepositInput(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        proof_of_possession=EMPTY_SIGNATURE,
    )

    if not bls.verify(
        pubkey=pubkey,
        # TODO: change to hash_tree_root(deposit_input) when we have SSZ tree hashing
        message=deposit_input.root,
        signature=proof_of_possession,
        domain=get_domain(
            state.fork_data,
            state.slot,
            SignatureDomain.DOMAIN_DEPOSIT,
        )
    ):
        raise ValidationError(
            "BLS signature verification error"
        )

    return True


def process_deposit(state: BeaconState,
                    pubkey: int,
                    deposit: int,
                    proof_of_possession: bytes,
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

    validator_pubkeys = tuple([v.pubkey for v in state.validator_registry])
    if pubkey not in validator_pubkeys:
        # Add new validator
        validator = ValidatorRecord(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            randao_layers=0,
            balance=deposit,
            status=ValidatorStatusCode.PENDING_ACTIVATION,
            latest_status_change_slot=state.slot,
            exit_count=0,
        )

        # Check if there's empty validator index
        index = min_empty_validator_index(
            state.validator_registry,
            state.slot,
            zero_balance_validator_ttl,
        )
        if index is None:
            # Append to the validator_registry
            with state.build_changeset() as state_changeset:
                state_changeset.validator_registry = (
                    state.validator_registry + (validator,)
                )
                state = state_changeset.commit()
            index = len(state.validator_registry) - 1
        else:
            # Use the empty validator index
            state = state.update_validator(index, validator)
    else:
        # Top-up - increase balance by deposit
        index = validator_pubkeys.index(pubkey)
        validator = state.validator_registry[index]

        if validator.withdrawal_credentials != validator.withdrawal_credentials:
            raise ValidationError(
                "`withdrawal_credentials` are incorrect:\n"
                "\texpected: %s, found: %s" % (
                    validator.withdrawal_credentials,
                    validator.withdrawal_credentials,
                )
            )

        # Update validator's balance and state
        with validator.build_changeset() as validator_changeset:
            validator_changeset.balance = validator.balance + deposit
            validator = validator_changeset.commit()
        state = state.update_validator(index, validator)

    return state, index
