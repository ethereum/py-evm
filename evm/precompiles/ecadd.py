from py_ecc import (
    optimized_bn128 as bn128,
)

from evm import constants
from evm.exceptions import (
    ValidationError,
    VMError,
)
from evm.utils.bn128 import (
    validate_point,
)
from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)
from evm.utils.padding import (
    pad32,
    pad32r,
)


def ecadd(computation):
    computation.gas_meter.consume_gas(constants.GAS_ECADD, reason='ECADD Precompile')

    try:
        result = _ecadd(computation.msg.data)
    except ValidationError:
        raise VMError("Invalid ECADD parameters")

    result_x, result_y = result
    result_bytes = b''.join((
        pad32(int_to_big_endian(result_x.n)),
        pad32(int_to_big_endian(result_y.n)),
    ))
    computation.output = result_bytes
    return computation


def _ecadd(data):
    x1_bytes = pad32r(data[:32])
    y1_bytes = pad32r(data[32:64])
    x2_bytes = pad32r(data[64:96])
    y2_bytes = pad32r(data[96:128])

    x1 = big_endian_to_int(x1_bytes)
    y1 = big_endian_to_int(y1_bytes)
    x2 = big_endian_to_int(x2_bytes)
    y2 = big_endian_to_int(y2_bytes)

    p1 = validate_point(x1, y1)
    p2 = validate_point(x2, y2)

    result = bn128.normalize(bn128.add(p1, p2))
    return result
