from __future__ import absolute_import
import functools
from typing import List  # noqa: F401

from eth import constants

from eth.vm.computation import BaseComputation


def log_XX(computation: BaseComputation, topic_count: int) -> None:
    if topic_count < 0 or topic_count > 4:
        raise TypeError("Invalid log topic size.  Must be 0, 1, 2, 3, or 4")

    mem_start_position, size = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    if not topic_count:
        topics = []  # type: List[int]
    elif topic_count > 1:
        topics = computation.stack_pop(num_items=topic_count, type_hint=constants.UINT256)
    else:
        topics = [computation.stack_pop(num_items=topic_count, type_hint=constants.UINT256)]

    data_gas_cost = constants.GAS_LOGDATA * size
    topic_gas_cost = constants.GAS_LOGTOPIC * topic_count
    total_gas_cost = data_gas_cost + topic_gas_cost

    computation.consume_gas(
        total_gas_cost,
        reason="Log topic and data gas cost",
    )

    computation.extend_memory(mem_start_position, size)
    log_data = computation.memory_read_bytes(mem_start_position, size)

    computation.add_log_entry(
        account=computation.msg.storage_address,
        topics=topics,
        data=log_data,
    )


log0 = functools.partial(log_XX, topic_count=0)
log1 = functools.partial(log_XX, topic_count=1)
log2 = functools.partial(log_XX, topic_count=2)
log3 = functools.partial(log_XX, topic_count=3)
log4 = functools.partial(log_XX, topic_count=4)
