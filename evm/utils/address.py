import rlp

from evm.validation import (
    validate_is_bytes,
    validate_length_lte,
)
from .keccak import (
    keccak,
)
from .padding import (
    pad_left,
)


def force_bytes_to_address(value):
    trimmed_value = value[-20:]
    padded_value = pad_left(trimmed_value, 20, b'\x00')
    return padded_value


def generate_contract_address(address, nonce):
    return keccak(rlp.encode([address, nonce]))[-20:]


def generate_CREATE2_contract_address(salt, code):
    """
    If contract is created by transaction, `salt` should be empty.
    If contract is created by contract, `salt` is set by the creator contract.
    """
    validate_length_lte(salt, 32, title="Salt")
    validate_is_bytes(salt)
    validate_is_bytes(code)

    return keccak(pad_left(salt, 32, b'\x00') + code)[-20:]
