import bisect

from evm.exceptions import (
    EVMNotFound,
)


def range_sort_fn(range):
    left, right = range
    if left is None:
        return -1
    return left


def find_range(ranges, block_number):
    # Special cases for the ends which *might* be open.
    if ranges[0][0] is None and ranges[0][1] is None:
        return ranges[0]
    elif ranges[0][1] is None:
        if block_number < ranges[0][0]:
            raise EVMNotFound(
                "There is no EVM available for block #{0}".format(block_number)
            )
        return ranges[0]
    elif block_number <= ranges[0][1]:
        if ranges[0][0] is not None and block_number < ranges[0][0]:
            raise EVMNotFound(
                "There is no EVM available for block #{0}".format(block_number)
            )
        return ranges[0]
    elif ranges[-1][0] is None:
        if block_number > ranges[-1][1]:
            raise EVMNotFound(
                "There is no EVM available for block #{0}".format(block_number)
            )
        return ranges[-1]
    elif block_number >= ranges[-1][0]:
        if ranges[-1][1] is not None and block_number > ranges[-1][1]:
            raise EVMNotFound(
                "There is no EVM available for block #{0}".format(block_number)
            )
        return ranges[-1]

    left_bounds, _ = zip(*ranges[1: -1])
    range_idx = bisect.bisect(left_bounds, block_number)
    return ranges[range_idx]
