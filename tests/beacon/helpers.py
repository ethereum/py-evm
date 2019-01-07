from eth_utils import to_tuple

from eth._utils import bls

from eth.constants import (
    ZERO_HASH32,
)
from eth.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth.beacon.types.deposit_input import DepositInput
from eth.beacon.types.validator_records import (
    ValidatorRecord,
)


def mock_validator_record(pubkey,
                          far_future_slot,
                          withdrawal_credentials=ZERO_HASH32,
                          randao_commitment=ZERO_HASH32,
                          status_flags=0,
                          is_active=True):
    return ValidatorRecord(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        randao_layers=0,
        activation_slot=0 if is_active else far_future_slot,
        exit_slot=far_future_slot,
        withdrawal_slot=far_future_slot,
        penalized_slot=far_future_slot,
        exit_count=0,
        status_flags=status_flags,
        custody_commitment=b'\x55' * 32,
        latest_custody_reseed_slot=0,
        penultimate_custody_reseed_slot=0,
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


def make_deposit_input(pubkey, withdrawal_credentials, randao_commitment, custody_commitment):
    return DepositInput(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        custody_commitment=custody_commitment,
        proof_of_possession=EMPTY_SIGNATURE,
    )
