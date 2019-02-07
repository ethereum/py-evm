from eth_typing import (
    Hash32,
)
from eth_utils import (
    ValidationError,
)

from eth2._utils import bls

from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.types.deposit_input import DepositInput
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validator_records import ValidatorRecord
from eth2.beacon.helpers import get_domain
from eth2.beacon.typing import (
    BLSPubkey,
    BLSSignature,
    ValidatorIndex,
    Gwei,
)


def validate_proof_of_possession(state: BeaconState,
                                 pubkey: BLSPubkey,
                                 proof_of_possession: BLSSignature,
                                 withdrawal_credentials: Hash32,
                                 randao_commitment: Hash32,
                                 epoch_length: int) -> None:
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
            state.fork,
            state.current_epoch(epoch_length),
            SignatureDomain.DOMAIN_DEPOSIT,
        ),
    )

    if not is_valid_signature:
        raise ValidationError(
            "BLS signature verification error"
        )


def add_pending_validator(state: BeaconState,
                          validator: ValidatorRecord,
                          amount: Gwei) -> BeaconState:
    """
    Add a validator to ``state``.
    """
    state = state.copy(
        validator_registry=state.validator_registry + (validator,),
        validator_balances=state.validator_balances + (amount, ),
    )

    return state


def process_deposit(*,
                    state: BeaconState,
                    pubkey: BLSPubkey,
                    amount: Gwei,
                    proof_of_possession: BLSSignature,
                    withdrawal_credentials: Hash32,
                    randao_commitment: Hash32,
                    epoch_length: int) -> BeaconState:
    """
    Process a deposit from Ethereum 1.0.
    """
    validate_proof_of_possession(
        state=state,
        pubkey=pubkey,
        proof_of_possession=proof_of_possession,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        epoch_length=epoch_length,
    )

    validator_pubkeys = tuple(v.pubkey for v in state.validator_registry)
    if pubkey not in validator_pubkeys:
        validator = ValidatorRecord.create_pending_validator(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
        )

        # Note: In phase 2 registry indices that has been withdrawn for a long time
        # will be recycled.
        state = add_pending_validator(
            state,
            validator,
            amount,
        )
    else:
        # Top-up - increase balance by deposit
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
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
        state = state.update_validator_balance(
            validator_index=index,
            balance=state.validator_balances[index] + amount,
        )

    return state
