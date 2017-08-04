import functools

from cytoolz.dicttoolz import (
    valfilter,
)
from cytoolz.functoolz import (
    partial,
    pipe,
)
from cytoolz.itertoolz import (
    isdistinct,
    frequencies,
)

from evm.constants import (
    UINT_256_MAX,
    SECPK1_N,
)
from evm.exceptions import (
    ValidationError,
)


def validate_is_bytes(value):
    if not isinstance(value, bytes):
        raise ValidationError("Value must be a byte string.  Got: {0}".format(type(value)))


def validate_is_integer(value):
    if not isinstance(value, int) or isinstance(value, bool):
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


def validate_length_lte(value, maximum_length):
    if len(value) > maximum_length:
        raise ValidationError(
            "Value must be of length less than or equal to {0}.  "
            "Got {1} of length {2}".format(
                maximum_length,
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
    validate_is_integer(value)


def validate_gt(value, minimum):
    if value <= minimum:
        raise ValidationError("Value {0} is not greater than {1}".format(value, minimum))
    validate_is_integer(value)


def validate_lte(value, maximum):
    if value > maximum:
        raise ValidationError(
            "Value {0} is not less than or equal to {1}".format(
                value, maximum,
            )
        )
    validate_is_integer(value)


def validate_lt(value, maximum):
    if value >= maximum:
        raise ValidationError("Value {0} is not less than {1}".format(value, maximum))
    validate_is_integer(value)


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


def validate_word(value):
    if not isinstance(value, bytes):
        raise ValidationError("Invalid word:  Must be of bytes type")
    elif not len(value) == 32:
        raise ValidationError("Invalid word:  Must be 32 bytes in length")


def validate_uint256(value):
    if not isinstance(value, int) or isinstance(value, bool):
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


def validate_unique(values):
    if not isdistinct(values):
        duplicates = pipe(
            values,
            frequencies,  # get the frequencies
            partial(valfilter, lambda v: v > 1),  # filter to ones that occure > 1
            sorted,  # sort them
            tuple,  # cast them to an immutiable form
        )
        raise ValidationError(
            "The values provided are not unique.  Duplicates: {0}".format(
                ', '.join((str(value) for value in duplicates))
            )
        )


def validate_block_number(block_number):
    validate_is_integer(block_number)
    validate_gte(block_number, 0)


def validate_vm_block_numbers(vm_block_numbers):
    validate_unique(vm_block_numbers)

    for block_number in vm_block_numbers:
        validate_block_number(block_number)
