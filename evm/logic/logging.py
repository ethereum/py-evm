from __future__ import absolute_import

import logging

from toolz import (
    partial,
)

from eth_utils import (
    pad_right,
)

from evm import constants
from evm.exceptions import (
    OutOfGas,
)

from evm.utils.address import (
    force_bytes_to_address,
)
from evm.utils.numeric import (
    ceil32,
    big_endian_to_int,
    int_to_big_endian,
)


logger = logging.getLogger('evm.logic.logging')


def log_XX(computation, topic_count):
    if topic_count < 0 or topic_count > 4:
        raise TypeError("Invalid log topic size.  Must be 0, 1, 2, 3, or 4")

    mem_start_position = big_endian_to_int(computation.stack.pop())
    size = big_endian_to_int(computation.stack.pop())

    topics = [computation.stack.pop() for _ in range(topic_count)]

    data_gas_cost = constants.GAS_LOGDATA * size
    topic_gas_cost = constants.GAS_LOGTOPIC * topic_count
    total_gas_cost = data_gas_cost + topic_gas_cost

    computation.gas_meter.consume_gas(total_gas_cost)
    if computation.gas_meter.is_out_of_gas:
        raise OutOfGas("Insufficient gas for log data")

    computation.extend_memory(mem_start_position, size)
    log_data = computation.memory.read(mem_start_position, size)

    computation.add_log_entry(
        account=computation.message.to,
        topics=topics,
        data=log_data,
    )

    logger.info(
        "LOG%s: topics: %s | data: %s",
        topic_count,
        b', '.join(topics),
        log_data,
    )


log0 = partial(log_XX, topic_count=0)
log1 = partial(log_XX, topic_count=1)
log2 = partial(log_XX, topic_count=2)
log3 = partial(log_XX, topic_count=3)
log4 = partial(log_XX, topic_count=4)
