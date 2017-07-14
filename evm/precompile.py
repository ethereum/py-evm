import hashlib

from evm import constants
from evm.ecc import get_ecc_backend
from evm.exceptions import (
    ValidationError,
)
from evm.validation import (
    validate_lt_secpk1n,
    validate_gte,
    validate_lte,
)

from evm.utils.address import (
    force_bytes_to_address,
    public_key_to_address,
)
from evm.utils.ecdsa import (
    BadSignature,
)
from evm.utils.numeric import (
    ceil32,
    big_endian_to_int,
)
from evm.utils.padding import (
    pad32,
    pad32r,
)
from evm.utils.secp256k1 import (
    encode_raw_public_key,
)


def precompiled_sha256(computation):
    word_count = ceil32(len(computation.msg.data)) // 32
    gas_fee = constants.GAS_SHA256 + word_count * constants.GAS_SHA256WORD

    computation.gas_meter.consume_gas(gas_fee, reason="SHA256 Precompile")
    input_bytes = computation.msg.data
    hash = hashlib.sha256(input_bytes).digest()
    computation.output = hash
    return computation


def precompile_ecrecover(computation):
    computation.gas_meter.consume_gas(constants.GAS_ECRECOVER, reason="ECRecover Precompile")
    raw_message_hash = computation.msg.data[:32]
    message_hash = pad32r(raw_message_hash)

    v_bytes = pad32r(computation.msg.data[32:64])
    v = big_endian_to_int(v_bytes)

    r_bytes = pad32r(computation.msg.data[64:96])
    r = big_endian_to_int(r_bytes)

    s_bytes = pad32r(computation.msg.data[96:128])
    s = big_endian_to_int(s_bytes)

    try:
        validate_lt_secpk1n(r)
        validate_lt_secpk1n(s)
        validate_lte(v, 28)
        validate_gte(v, 27)
    except ValidationError:
        return computation

    try:
        raw_public_key = get_ecc_backend().ecdsa_raw_recover(message_hash, (v, r, s))
    except BadSignature:
        return computation

    public_key = encode_raw_public_key(raw_public_key)
    address = public_key_to_address(public_key)
    padded_address = pad32(address)

    computation.output = padded_address
    return computation


def precompile_identity(computation):
    word_count = ceil32(len(computation.msg.data)) // 32
    gas_fee = constants.GAS_IDENTITY + word_count * constants.GAS_IDENTITYWORD

    computation.gas_meter.consume_gas(gas_fee, reason="Identity Precompile")

    computation.output = computation.msg.data
    return computation


def precompile_ripemd160(computation):
    word_count = ceil32(len(computation.msg.data)) // 32
    gas_fee = constants.GAS_RIPEMD160 + word_count * constants.GAS_RIPEMD160WORD

    computation.gas_meter.consume_gas(gas_fee, reason="RIPEMD160 Precompile")

    # TODO: this only works if openssl is installed.
    hash = hashlib.new('ripemd160', computation.msg.data).digest()
    padded_hash = pad32(hash)
    computation.output = padded_hash
    return computation


PRECOMPILES = {
    force_bytes_to_address(b'\x01'): precompile_ecrecover,
    force_bytes_to_address(b'\x02'): precompiled_sha256,
    force_bytes_to_address(b'\x03'): precompile_ripemd160,
    force_bytes_to_address(b'\x04'): precompile_identity,
}
