from evm import constants
from evm.utils.numeric import (
    ceil32,
)


def identity(computation):
    word_count = ceil32(len(computation.msg.data)) // 32
    gas_fee = constants.GAS_IDENTITY + word_count * constants.GAS_IDENTITYWORD

    computation.gas_meter.consume_gas(gas_fee, reason="Identity Precompile")

    computation.output = computation.msg.data
    return computation
