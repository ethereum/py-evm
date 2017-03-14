from toolz import (
    partial,
    juxt,
)

from eth_utils import (
    is_bytes,
    is_canonical_address,
)

from evm.constants import (
    UINT_256_MAX,
)


def validate_is_bytes(value):
    if not is_bytes(value):
        raise TypeError("Value must be a byte string.  Got: {0}".format(type(value)))


def validate_length(value, length):
    if not len(value) == length:
        raise TypeError(
            "Value must be of length {0}.  Got {1} of length {2}".format(
                length,
                value,
                len(value),
            )
        )


def validate_gte(value, minimum):
    if value < minimum:
        raise TypeError(
            "Value {0} is not greater than or equal to {1}".format(
                value, minimum,
            )
        )


def validate_lte(value, maximum):
    if value > maximum:
        raise TypeError(
            "Value {0} is not less than or equal to {1}".format(
                value, maximum,
            )
        )


def validate_canonical_address(value):
    if not is_canonical_address(value):
        raise TypeError(
            "Value {0} is not a valid canonical address"
        )


validate_word = juxt(
    validate_is_bytes,
    partial(validate_length, length=32),
)
validate_uint256 = juxt(
    partial(validate_gte, minimum=0),
    partial(validate_lte, maximum=UINT_256_MAX),
)
