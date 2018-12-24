from eth_utils import to_tuple

from eth._utils import bls

from eth.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth.beacon.enums import (
    ValidatorStatusCode,
)
from eth.beacon.types.deposit_input import DepositInput
from eth.beacon.types.validator_records import (
    ValidatorRecord,
)


def mock_validator_record(pubkey):
    return ValidatorRecord(
        pubkey=pubkey,
        withdrawal_credentials=b'\x44' * 32,
        randao_commitment=b'\x55' * 32,
        randao_layers=0,
        status=ValidatorStatusCode.ACTIVE,
        latest_status_change_slot=0,
        exit_count=0,
    )


@to_tuple
def get_pseudo_chain(length, genesis_block):
    """
    Get a pseudo chain, only slot and parent_root are valid.
    """
    block = genesis_block.copy()
    yield block
    for slot in range(1, length * 3):
        block = genesis_block.copy(
            slot=slot,
            parent_root=block.root
        )
        yield block


def sign_proof_of_possession(deposit_input, privkey, domain):
    return bls.sign(deposit_input.root, privkey, domain)


def make_deposit_input(pubkey, withdrawal_credentials, randao_commitment):
    return DepositInput(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        proof_of_possession=EMPTY_SIGNATURE,
    )
