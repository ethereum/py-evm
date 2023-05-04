import hashlib

from eth import (
    constants,
)
from eth._utils.numeric import (
    ceil32,
)
from eth._utils.padding import (
    pad32,
)
from eth.abc import (
    ComputationAPI,
)


def ripemd160(computation: ComputationAPI) -> ComputationAPI:
    word_count = ceil32(len(computation.msg.data)) // 32
    gas_fee = constants.GAS_RIPEMD160 + word_count * constants.GAS_RIPEMD160WORD

    computation.consume_gas(gas_fee, reason="RIPEMD160 Precompile")

    # TODO: this only works if openssl is installed.
    hash = hashlib.new("ripemd160", computation.msg.data).digest()
    padded_hash = pad32(hash)
    computation.output = padded_hash
    return computation
