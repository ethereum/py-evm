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


def ecmul(computation):
    computation.gas_meter.consume_gas(constants.GAS_ECMUL, reason='ECMUL Precompile')

    try:
        result = _ecmull(computation.msg.data)
    except ValidationError:
        raise VMError("Invalid ECMUL parameters")

    result_x, result_y = result
    result_bytes = b''.join((
        pad32(int_to_big_endian(result_x.n)),
        pad32(int_to_big_endian(result_y.n)),
    ))
    computation.output = result_bytes
    return computation


def _ecmull(data):
    x_bytes = pad32r(data[:32])
    y_bytes = pad32r(data[32:64])
    m_bytes = pad32r(data[64:96])

    x = big_endian_to_int(x_bytes)
    y = big_endian_to_int(y_bytes)
    m = big_endian_to_int(m_bytes)

    p = validate_point(x, y)

    result = bn128.normalize(bn128.multiply(p, m))
    return result
