from eth_utils import (
    ValidationError,
)
from py_ecc import bls
import ssz

from eth2._utils.hash import (
    hash_eth2,
)
from eth2._utils.merkle.common import (
    verify_merkle_branch,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.helpers import get_domain
from eth2.beacon.typing import (
    ValidatorIndex,
    Gwei,
)


def add_pending_validator(state: BeaconState,
                          validator: Validator,
                          amount: Gwei) -> BeaconState:
    """
    Add a validator to ``state``.
    """
    state = state.copy(
        validator_registry=state.validator_registry + (validator,),
        validator_balances=state.validator_balances + (amount, ),
    )

    return state


#
# Deposits
#
def validate_deposit(state: BeaconState,
                     deposit: Deposit,
                     deposit_contract_tree_depth: int) -> None:
    validate_deposit_order(state, deposit)
    validate_deposit_proof(state, deposit, deposit_contract_tree_depth)


def validate_deposit_order(state: BeaconState,
                           deposit: Deposit) -> None:
    """
    Validate if deposits processed in order.
    """
    if deposit.index != state.deposit_index:
        raise ValidationError(
            f"deposit.index ({deposit.index}) is not equal to "
            f"state.deposit_index ({state.deposit_index})"
        )


def validate_deposit_proof(state: BeaconState,
                           deposit: Deposit,
                           deposit_contract_tree_depth: int) -> None:
    """
    Validate if deposit branch proof is valid.
    """
    # Should equal 8 bytes for deposit_data.amount +
    #              8 bytes for deposit_data.timestamp +
    #              176 bytes for deposit_data.deposit_input
    # It should match the deposit_data in the eth1.0 deposit contract
    serialized_deposit_data = ssz.encode(deposit.deposit_data)

    is_valid_proof = verify_merkle_branch(
        leaf=hash_eth2(serialized_deposit_data),
        proof=deposit.proof,
        depth=deposit_contract_tree_depth,
        index=deposit.index,
        root=state.latest_eth1_data.deposit_root,
    )
    if not is_valid_proof:
        raise ValidationError(
            f"deposit.proof ({deposit.proof}) is invalid against "
            f"leaf={hash_eth2(serialized_deposit_data)}, "
            f"deposit_contract_tree_depth={deposit_contract_tree_depth}, "
            f"deposit.index={deposit.index} "
            f"state.latest_eth1_data.deposit_root={state.latest_eth1_data.deposit_root.hex()}"
        )


def process_deposit(state: BeaconState,
                    deposit: Deposit,
                    slots_per_epoch: int,
                    deposit_contract_tree_depth: int) -> BeaconState:
    """
    Process a deposit from Ethereum 1.0.
    """
    validate_deposit(state, deposit, deposit_contract_tree_depth)

    # Increment the next deposit index we are expecting. Note that this
    # needs to be done here because while the deposit contract will never
    # create an invalid Merkle branch, it may admit an invalid deposit
    # object, and we need to be able to skip over it
    state = state.copy(
        deposit_index=state.deposit_index + 1,
    )

    validator_pubkeys = tuple(v.pubkey for v in state.validator_registry)
    deposit_input = deposit.deposit_data.deposit_input
    pubkey = deposit_input.pubkey
    amount = deposit.deposit_data.amount
    withdrawal_credentials = deposit_input.withdrawal_credentials

    if pubkey not in validator_pubkeys:
        # Verify the proof of possession
        proof_is_valid = bls.verify(
            pubkey=pubkey,
            message_hash=deposit_input.signing_root,
            signature=deposit_input.signature,
            domain=get_domain(
                state.fork,
                state.current_epoch(slots_per_epoch),
                SignatureDomain.DOMAIN_DEPOSIT,
            ),
        )
        if not proof_is_valid:
            return state

        validator = Validator.create_pending_validator(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
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

        # Update validator's balance and state
        state = state.update_validator_balance(
            validator_index=index,
            balance=state.validator_balances[index] + amount,
        )

    return state
