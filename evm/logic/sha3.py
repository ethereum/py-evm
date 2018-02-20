from eth_utils import (
    keccak,
)

from evm import constants
from evm.utils.numeric import (
    ceil32,
)


def sha3(computation):
    start_position, size = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    sha3_bytes = computation.memory.read(start_position, size)
    word_count = ceil32(len(sha3_bytes)) // 32

    gas_cost = constants.GAS_SHA3WORD * word_count
    computation.gas_meter.consume_gas(gas_cost, reason="SHA3: word gas cost")

    result = keccak(sha3_bytes)

    computation.stack.push(result)
