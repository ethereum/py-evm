import rlp

from eth_utils import (
    keccak,
)

from evm.validation import (
    validate_is_bytes,
    validate_length_lte,
)


def force_bytes_to_address(value):
    trimmed_value = value[-20:]
    padded_value = trimmed_value.rjust(20, b'\x00')
    return padded_value


def generate_contract_address(address, nonce):
    return keccak(rlp.encode([address, nonce]))[-20:]


def generate_CREATE2_contract_address(salt, code):
    """
    If contract is created by transaction, `salt` is specified by `transaction.salt`.
    If contract is created by contract, `salt` is set by the creator contract.
    """
    validate_length_lte(salt, 32, title="Salt")
    validate_is_bytes(salt)
    validate_is_bytes(code)

    return keccak(salt.rjust(32, b'\x00') + code)[-20:]
