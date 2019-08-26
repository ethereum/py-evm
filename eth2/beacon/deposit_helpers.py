from eth_utils import ValidationError, encode_hex

from eth2._utils.bls import bls
from eth2._utils.merkle.common import verify_merkle_branch
from eth2.beacon.constants import DEPOSIT_CONTRACT_TREE_DEPTH
from eth2.beacon.epoch_processing_helpers import increase_balance
from eth2.beacon.helpers import compute_domain
from eth2.beacon.signature_domain import SignatureDomain
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import ValidatorIndex
from eth2.configs import Eth2Config


def validate_deposit_proof(
    state: BeaconState, deposit: Deposit, deposit_contract_tree_depth: int
) -> None:
    """
    Validate if deposit branch proof is valid.
    """
    is_valid_proof = verify_merkle_branch(
        leaf=deposit.data.hash_tree_root,
        proof=deposit.proof,
        depth=deposit_contract_tree_depth + 1,
        index=state.eth1_deposit_index,
        root=state.eth1_data.deposit_root,
    )
    if not is_valid_proof:
        raise ValidationError(
            f"deposit.proof ({list(map(encode_hex, deposit.proof))}) is invalid against "
            f"leaf={encode_hex(deposit.data.hash_tree_root)}, "
            f"deposit_contract_tree_depth={deposit_contract_tree_depth}, "
            f"deposit.index (via state) = {state.eth1_deposit_index} "
            f"state.eth1_data.deposit_root={state.eth1_data.deposit_root.hex()}"
        )


def process_deposit(
    state: BeaconState, deposit: Deposit, config: Eth2Config
) -> BeaconState:
    """
    Process a deposit from Ethereum 1.0.
    """
    validate_deposit_proof(state, deposit, DEPOSIT_CONTRACT_TREE_DEPTH)

    # Increment the next deposit index we are expecting. Note that this
    # needs to be done here because while the deposit contract will never
    # create an invalid Merkle branch, it may admit an invalid deposit
    # object, and we need to be able to skip over it
    state = state.copy(eth1_deposit_index=state.eth1_deposit_index + 1)

    pubkey = deposit.data.pubkey
    amount = deposit.data.amount
    validator_pubkeys = tuple(v.pubkey for v in state.validators)
    if pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) for new validators.
        # Note: The deposit contract does not check signatures.
        # Note: Deposits are valid across forks, thus the deposit domain
        # is retrieved directly from `compute_domain`.
        is_valid_proof_of_possession = bls.verify(
            message_hash=deposit.data.signing_root,
            pubkey=pubkey,
            signature=deposit.data.signature,
            domain=compute_domain(SignatureDomain.DOMAIN_DEPOSIT),
        )
        if not is_valid_proof_of_possession:
            return state

        withdrawal_credentials = deposit.data.withdrawal_credentials
        validator = Validator.create_pending_validator(
            pubkey, withdrawal_credentials, amount, config
        )

        return state.copy(
            validators=state.validators + (validator,),
            balances=state.balances + (amount,),
        )
    else:
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
        return increase_balance(state, index, amount)
