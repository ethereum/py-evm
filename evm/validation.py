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
    GAS_LIMIT_ADJUSTMENT_FACTOR,
    GAS_LIMIT_MAXIMUM,
    GAS_LIMIT_MINIMUM,
    SECPK1_N,
    UINT_256_MAX,
)
from evm.exceptions import (
    ValidationError,
)


def validate_is_bytes(value, title="Value"):
    if not isinstance(value, bytes):
        raise ValidationError(
            "{title} must be a byte string.  Got: {0}".format(type(value), title=title)
        )


def validate_is_integer(value, title="Value"):
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            "{title} must be a an integer.  Got: {0}".format(type(value), title=title)
        )


def validate_length(value, length, title="Value"):
    if not len(value) == length:
        raise ValidationError(
            "{title} must be of length {0}.  Got {1} of length {2}".format(
                length,
                value,
                len(value),
                title=title,
            )
        )


def validate_length_lte(value, maximum_length, title="Value"):
    if len(value) > maximum_length:
        raise ValidationError(
            "{title} must be of length less than or equal to {0}.  "
            "Got {1} of length {2}".format(
                maximum_length,
                value,
                len(value),
                title=title,
            )
        )


def validate_gte(value, minimum, title="Value"):
    if value < minimum:
        raise ValidationError(
            "{title} {0} is not greater than or equal to {1}".format(
                value,
                minimum,
                title=title,
            )
        )
    validate_is_integer(value)


def validate_gt(value, minimum, title="Value"):
    if value <= minimum:
        raise ValidationError(
            "{title} {0} is not greater than {1}".format(value, minimum, title=title)
        )
    validate_is_integer(value, title=title)


def validate_lte(value, maximum, title="Value"):
    if value > maximum:
        raise ValidationError(
            "{title} {0} is not less than or equal to {1}".format(
                value,
                maximum,
                title=title,
            )
        )
    validate_is_integer(value, title=title)


def validate_lt(value, maximum, title="Value"):
    if value >= maximum:
        raise ValidationError(
            "{title} {0} is not less than {1}".format(value, maximum, title=title)
        )
    validate_is_integer(value, title=title)


def validate_canonical_address(value, title="Value"):
    if not isinstance(value, bytes) or not len(value) == 20:
        raise ValidationError(
            "{title} {0} is not a valid canonical address".format(value, title=title)
        )


def validate_multiple_of(value, multiple_of, title="Value"):
    if not value % multiple_of == 0:
        raise ValidationError(
            "{title} {0} is not a multiple of {1}".format(value, multiple_of, title=title)
        )


def validate_is_boolean(value, title="Value"):
    if not isinstance(value, bool):
        raise ValidationError(
            "{title} must be an boolean.  Got type: {0}".format(type(value), title=title)
        )


def validate_word(value, title="Value"):
    if not isinstance(value, bytes):
        raise ValidationError(
            "{title} is not a valid word. Must be of bytes type: Got: {0}".format(
                type(value),
                title=title,
            )
        )
    elif not len(value) == 32:
        raise ValidationError(
            "{title} is not a valid word. Must be 32 bytes in length: Got: {0}".format(
                len(value),
                title=title,
            )
        )


def validate_uint256(value, title="Value"):
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            "{title} must be an integer: Got: {0}".format(
                type(value),
                title=title,
            )
        )
    if value < 0:
        raise ValidationError(
            "{title} cannot be negative: Got: {0}".format(
                value,
                title=title,
            )
        )
    if value > UINT_256_MAX:
        raise ValidationError(
            "{title} exeeds maximum UINT256 size.  Got: {0}".format(
                value,
                title=title,
            )
        )


def validate_stack_item(value):
    if isinstance(value, bytes) and len(value) <= 32:
        return
    elif isinstance(value, int) and 0 <= value <= UINT_256_MAX:
        return
    raise ValidationError(
        "Invalid Stack Item: Must be either a length 32 byte "
        "string or a 256 bit integer. Got {0}".format(value)
    )


validate_lt_secpk1n = functools.partial(validate_lte, maximum=SECPK1_N - 1)
validate_lt_secpk1n2 = functools.partial(validate_lte, maximum=SECPK1_N // 2 - 1)


def validate_unique(values, title="Value"):
    if not isdistinct(values):
        duplicates = pipe(
            values,
            frequencies,  # get the frequencies
            partial(valfilter, lambda v: v > 1),  # filter to ones that occure > 1
            sorted,  # sort them
            tuple,  # cast them to an immutiable form
        )
        raise ValidationError(
            "{title} does not contain unique items.  Duplicates: {0}".format(
                ', '.join((str(value) for value in duplicates)),
                title=title,
            )
        )


def validate_block_number(block_number, title="Block Number"):
    validate_is_integer(block_number, title="Block Number")
    validate_gte(block_number, 0, title="Block Number")


def validate_vm_block_numbers(vm_block_numbers):
    validate_unique(vm_block_numbers, title="Block Number set")

    for block_number in vm_block_numbers:
        validate_block_number(block_number)


def validate_gas_limit(gas_limit, parent_gas_limit):
    if gas_limit < GAS_LIMIT_MINIMUM:
        raise ValidationError("Gas limit {0} is below minimum {1}".format(
            gas_limit, GAS_LIMIT_MINIMUM))
    if gas_limit > GAS_LIMIT_MAXIMUM:
        raise ValidationError("Gas limit {0} is above maximum {1}".format(
            gas_limit, GAS_LIMIT_MAXIMUM))
    diff = gas_limit - parent_gas_limit
    if diff > (parent_gas_limit // GAS_LIMIT_ADJUSTMENT_FACTOR):
        raise ValidationError(
            "Gas limit {0} difference to parent {1} is too big {2}".format(
                gas_limit, parent_gas_limit, diff))


ALLOWED_HEADER_FIELDS = {
    'coinbase',
    'gas_limit',
    'timestamp',
    'extra_data',
    'mix_hash',
    'nonce',
    'uncles_hash',
    'transaction_root',
    'receipt_root',
}


def validate_header_params_for_configuration(header_params):
    extra_fields = set(header_params.keys()).difference(ALLOWED_HEADER_FIELDS)
    if extra_fields:
        raise ValidationError(
            "The `configure_header` method may only be used with the fields ({0}). "
            "The provided fields ({1}) are not supported".format(
                ", ".join(tuple(sorted(ALLOWED_HEADER_FIELDS))),
                ", ".join(tuple(sorted(extra_fields))),
            )
        )


def validate_transaction_access_list(access_list, title="Access List"):
    for item in access_list:
        if len(item) == 0:
            raise ValidationError(
                "{0} entry must at least specify an account address.".format(title)
            )
        address, *prefixes = item
        validate_canonical_address(address, title="Address in {0}".format(title))
        for prefix in prefixes:
            validate_is_bytes(prefix, title="Storage prefix in {0}".format(title))
            if len(prefix) > 32:
                raise ValidationError(
                    "Storage prefix in {0} must be 32 bytes or shorter. Got: {1}".format(
                        title,
                        prefix,
                    )
                )


def validate_access_list(access_list):
    for entry in access_list:
        validate_is_bytes(entry, "Access prefix")


def validate_sig_hash(sig_hash, title="Sig Hash"):
    validate_is_bytes(sig_hash, title)
    validate_length(sig_hash, 32, title)
