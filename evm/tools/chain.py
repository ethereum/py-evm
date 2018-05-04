import collections
import operator

from evm.validation import (
    validate_vm_block_numbers,
)

from evm.vm import VM

from collections import OrderedDict
from typing import Tuple, Type


def generate_vms_by_range(vm_configuration: Tuple[Tuple[int, Type[VM]]]) -> OrderedDict:
    validate_vm_block_numbers(tuple(
        block_number
        for block_number, _
        in vm_configuration
    ))

    # Organize the Chain classes by their starting blocks.
    vms_by_range = collections.OrderedDict(
        sorted(vm_configuration, key=operator.itemgetter(0))
    )
    return vms_by_range
