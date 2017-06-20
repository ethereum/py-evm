import functools
import itertools

from evm.constants import (
    UINT_256_MAX,
    SECPK1_N,
)
from evm.exceptions import (
    ValidationError,
)

from evm.utils.ranges import (
    range_sort_fn,
)


def validate_is_bytes(value):
    if not isinstance(value, bytes):
        raise ValidationError("Value must be a byte string.  Got: {0}".format(type(value)))


def validate_is_integer(value):
    if not isinstance(value, int):
        raise ValidationError("Value must be a an integer.  Got: {0}".format(type(value)))


def validate_length(value, length):
    if not len(value) == length:
        raise ValidationError(
            "Value must be of length {0}.  Got {1} of length {2}".format(
                length,
                value,
                len(value),
            )
        )


def validate_gte(value, minimum):
    if value < minimum:
        raise ValidationError(
            "Value {0} is not greater than or equal to {1}".format(
                value, minimum,
            )
        )


def validate_gt(value, minimum):
    if value <= minimum:
        raise ValidationError("Value {0} is not greater than {1}".format(value, minimum))


def validate_lte(value, maximum):
    if value > maximum:
        raise ValidationError(
            "Value {0} is not less than or equal to {1}".format(
                value, maximum,
            )
        )


def validate_lt(value, maximum):
    if value >= maximum:
        raise ValidationError("Value {0} is not less than {1}".format(value, maximum))


def validate_canonical_address(value):
    if not isinstance(value, bytes) or not len(value) == 20:
        raise ValidationError(
            "Value {0} is not a valid canonical address".format(value)
        )


def validate_multiple_of(value, multiple_of):
    if not value % multiple_of == 0:
        raise ValidationError(
            "Value {0} is not a multiple of {1}".format(value, multiple_of)
        )


def validate_is_boolean(value):
    if not isinstance(value, bool):
        raise ValidationError("Value must be an boolean.  Got type: {0}".format(type(value)))


validate_multiple_of_8 = functools.partial(validate_multiple_of, multiple_of=8)


def validate_word(value):
    if not isinstance(value, bytes):
        raise ValidationError("Invalid word:  Must be of bytes type")
    elif not len(value) == 32:
        raise ValidationError("Invalid word:  Must be 32 bytes in length")


def validate_uint256(value):
    if not isinstance(value, int):
        raise ValidationError("Invalid UINT256: Must be an integer")
    if value < 0:
        raise ValidationError("Invalid UINT256: Value is negative")
    if value > UINT_256_MAX:
        raise ValidationError("Invalid UINT256: Value is greater than 2**256 - 1")


def validate_stack_item(value):
    if isinstance(value, bytes) and len(value) <= 32:
        return
    elif isinstance(value, int) and 0 <= value <= UINT_256_MAX:
        return
    raise ValidationError("Invalid bytes or UINT256")


validate_lt_secpk1n = functools.partial(validate_lte, maximum=SECPK1_N - 1)
validate_lt_secpk1n2 = functools.partial(validate_lte, maximum=SECPK1_N // 2 - 1)


def validate_vm_block_ranges(ranges):
    """
    Given an iterable of inclusive ranges formatted as 2-tuples
    of [left_bound, right_bound] where `left_bound` and `right_bound` are
    either integers or `None` to represent and open-ended range, validate all
    of the following properties.

    - Non empty
    - There is at most 1 open left bound
    - There is at most 1 open right bound
    - There are no ranges which intersect
    - There are no gaps between the ranges
    """
    if not ranges:
        raise ValidationError("Must be at least one range")

    # Make sure it's an iterable of length two iterables
    if not all(len(range) == 2 for range in ranges):
        raise ValidationError("Ranges must be iterables of length two")

    # Make sure all range values are either integers or None
    for bound in itertools.chain.from_iterable(ranges):
        if bound is None:
            continue
        elif isinstance(bound, int):
            validate_uint256(bound)
        else:
            raise ValidationError("All range bounds must be either None or an integer")

    # Split into two iterables of all left bounds and all right bounds.
    left_bounds, right_bounds = zip(*ranges)
    has_open_left_bound = any(left is None for left in left_bounds)
    has_open_right_bound = any(right is None for right in right_bounds)

    # make sure that there is at most one range open on the left.
    if has_open_left_bound:
        iter_left_bounds = (left is None for left in left_bounds)
        if not (any(iter_left_bounds) and not any(iter_left_bounds)):
            raise ValidationError("More than one range has an open left bound")

    # make sure that there is at most one range open on the right.
    if has_open_right_bound:
        iter_right_bounds = (right is None for right in right_bounds)
        if not (any(iter_right_bounds) and not any(iter_right_bounds)):
            raise ValidationError("More than one range has an open right bound")

    # check that there are no intersecting ranges.
    sorted_ranges = tuple(sorted(ranges, key=range_sort_fn))
    for range_a, range_b in zip(sorted_ranges, sorted_ranges[1:]):
        to_check = itertools.chain(
            itertools.product(range_a, [range_b]),
            itertools.product(range_b, [range_a]),
        )
        for bound, (left, right) in to_check:
            if bound is None:
                continue
            elif left is None:
                if bound <= right:
                    raise ValidationError("Ranges have intersection")
            elif right is None:
                if bound >= left:
                    raise ValidationError("Ranges have intersection")
            else:
                if left <= bound <= right:
                    raise ValidationError("Ranges have intersection")

        # Check that there is not a gap between the ranges.
        _, right_a = range_a
        left_b, _ = range_b
        if right_a + 1 != left_b:
            raise ValidationError("Ranges have gap")
