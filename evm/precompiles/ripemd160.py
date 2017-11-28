import hashlib

from evm import constants

from evm.utils.numeric import (
    ceil32,
)
from evm.utils.padding import (
    pad32,
)


def ripemd160(computation):
    word_count = ceil32(len(computation.msg.data)) // 32
    gas_fee = constants.GAS_RIPEMD160 + word_count * constants.GAS_RIPEMD160WORD

    computation.gas_meter.consume_gas(gas_fee, reason="RIPEMD160 Precompile")

    # TODO: this only works if openssl is installed.
    hash = hashlib.new('ripemd160', computation.msg.data).digest()
    padded_hash = pad32(hash)
    computation.output = padded_hash
    return computation
