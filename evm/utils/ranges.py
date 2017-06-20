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
    #
    # Special cases for open ended ranges.
    #
    if ranges[0][0] is None and ranges[0][1] is None:
        # Case: single range open on both ends.
        return ranges[0]
    elif ranges[0][1] is None:
        # Case: single range open on upper bound.
        if block_number < ranges[0][0]:
            raise EVMNotFound(
                "There is no EVM available for block #{0}".format(block_number)
            )
        return ranges[0]
    elif block_number <= ranges[0][1]:
        # Case: first range upper bound is gte block number.
        if ranges[0][0] is not None and block_number < ranges[0][0]:
            raise EVMNotFound(
                "There is no EVM available for block #{0}".format(block_number)
            )
        return ranges[0]
    elif ranges[-1][0] is None:
        # Case: last range lower bound is open.
        if block_number > ranges[-1][1]:
            raise EVMNotFound(
                "There is no EVM available for block #{0}".format(block_number)
            )
        return ranges[-1]
    elif block_number >= ranges[-1][0]:
        # Case: last range lower bound is lte block number.
        if ranges[-1][1] is not None and block_number > ranges[-1][1]:
            raise EVMNotFound(
                "There is no EVM available for block #{0}".format(block_number)
            )
        return ranges[-1]

    # No special cases were found so we can do a binary search across the
    # closed ranges.
    left_bounds, _ = zip(*ranges[1: -1])
    range_idx = bisect.bisect(left_bounds, block_number)
    return ranges[range_idx]
