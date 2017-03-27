from toolz import (
    partial,
    juxt,
)

from evm.constants import (
    UINT_256_MAX,
)
from evm.exceptions import (
    ValidationError,
)
from evm.opcodes import (
    KNOWN_OPCODES,
)


def validate_is_bytes(value):
    if not isinstance(value, (bytes, bytearray)):
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


def validate_lte(value, maximum):
    if value > maximum:
        raise ValidationError(
            "Value {0} is not less than or equal to {1}".format(
                value, maximum,
            )
        )


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


def validate_boolean(value):
    if not isinstance(value, bool):
        raise ValidationError("Value must be an boolean.  Got type: {0}".format(type(value)))


def validate_opcode(value):
    if not isinstance(value, int):
        raise ValidationError("Opcodes must be integers")
    if value not in KNOWN_OPCODES:
        raise ValidationError("Value {0} is not a known opcode.".format(hex(value)))


validate_multiple_of_8 = partial(validate_multiple_of, multiple_of=8)


def validate_word(value):
    if not isinstance(value, (bytes, bytearray)):
        raise ValidationError("Invalid word:  Must be of bytes type")
    elif not len(value) == 32:
        raise ValidationError("Invalid word:  Must be 32 bytes in length")


def validate_uint256(value):
    if value < 0:
        raise ValidationError("Invalid UINT256: Value is negative")
    if value > UINT_256_MAX:
        raise ValidationError("Invalid UINT256: Value is greater than 2**256 - 1")


def validate_stack_item(value):
    if isinstance(value, (bytes, bytearray)) and len(value) <= 32:
        return
    elif isinstance(value, int) and 0 <= value <= UINT_256_MAX:
        return
    raise ValidationError("Invalid bytes or UINT256")
