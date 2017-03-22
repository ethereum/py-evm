from toolz import (
    partial,
    juxt,
)

from eth_utils import (
    is_bytes,
    is_integer,
    is_boolean,
    is_canonical_address,
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
    if not is_bytes(value):
        raise ValidationError("Value must be a byte string.  Got: {0}".format(type(value)))


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
    if not is_canonical_address(value):
        raise ValidationError(
            "Value {0} is not a valid canonical address".format(value)
        )


def validate_multiple_of(value, multiple_of):
    if not value % multiple_of == 0:
        raise ValidationError(
            "Value {0} is not a multiple of {1}".format(value, multiple_of)
        )


def validate_integer(value):
    if not is_integer(value):
        raise ValidationError("Value must be an integer.  Got type: {0}".format(type(value)))


def validate_boolean(value):
    if not is_boolean(value):
        raise ValidationError("Value must be an boolean.  Got type: {0}".format(type(value)))


def validate_opcode(value):
    validate_integer(value)
    if value not in KNOWN_OPCODES:
        raise ValidationError("Value {0} is not a known opcode.".format(hex(value)))


validate_multiple_of_8 = partial(validate_multiple_of, multiple_of=8)

validate_word = juxt(
    validate_is_bytes,
    partial(validate_length, length=32),
)
validate_uint256 = juxt(
    partial(validate_gte, minimum=0),
    partial(validate_lte, maximum=UINT_256_MAX),
)
