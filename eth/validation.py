import functools

from typing import (
    Any,
    Dict,
    Iterable,
    Sequence,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)

from eth_typing import (
    Address,
    Hash32,
)

from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import dicttoolz

from eth_utils.toolz import functoolz

from eth_utils.toolz import itertoolz

from eth.constants import (
    GAS_LIMIT_ADJUSTMENT_FACTOR,
    GAS_LIMIT_MAXIMUM,
    GAS_LIMIT_MINIMUM,
    SECPK1_N,
    UINT_256_MAX,
)

from eth.typing import (
    BytesOrView,
)

if TYPE_CHECKING:
    from eth.vm.base import BaseVM      # noqa: F401


def validate_is_bytes(value: bytes, title: str="Value") -> None:
    if not isinstance(value, bytes):
        raise ValidationError(
            "{title} must be a byte string.  Got: {0}".format(type(value), title=title)
        )


def validate_is_bytes_or_view(value: BytesOrView, title: str="Value") -> None:
    if isinstance(value, (bytes, memoryview)):
        return
    raise ValidationError(
        "{title} must be bytes or memoryview. Got {0}".format(type(value), title=title)
    )


def validate_is_integer(value: Union[int, bool], title: str="Value") -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            "{title} must be a an integer.  Got: {0}".format(type(value), title=title)
        )


def validate_length(value: Sequence[Any], length: int, title: str="Value") -> None:
    if not len(value) == length:
        raise ValidationError(
            "{title} must be of length {0}.  Got {1} of length {2}".format(
                length,
                value,
                len(value),
                title=title,
            )
        )


def validate_length_lte(value: Sequence[Any], maximum_length: int, title: str="Value") -> None:
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


def validate_gte(value: int, minimum: int, title: str="Value") -> None:
    if value < minimum:
        raise ValidationError(
            "{title} {0} is not greater than or equal to {1}".format(
                value,
                minimum,
                title=title,
            )
        )
    validate_is_integer(value)


def validate_gt(value: int, minimum: int, title: str="Value") -> None:
    if value <= minimum:
        raise ValidationError(
            "{title} {0} is not greater than {1}".format(value, minimum, title=title)
        )
    validate_is_integer(value, title=title)


def validate_lte(value: int, maximum: int, title: str="Value") -> None:
    if value > maximum:
        raise ValidationError(
            "{title} {0} is not less than or equal to {1}".format(
                value,
                maximum,
                title=title,
            )
        )
    validate_is_integer(value, title=title)


def validate_lt(value: int, maximum: int, title: str="Value") -> None:
    if value >= maximum:
        raise ValidationError(
            "{title} {0} is not less than {1}".format(value, maximum, title=title)
        )
    validate_is_integer(value, title=title)


def validate_canonical_address(value: Address, title: str="Value") -> None:
    if not isinstance(value, bytes) or not len(value) == 20:
        raise ValidationError(
            "{title} {0} is not a valid canonical address".format(value, title=title)
        )


def validate_multiple_of(value: int, multiple_of: int, title: str="Value") -> None:
    if not value % multiple_of == 0:
        raise ValidationError(
            "{title} {0} is not a multiple of {1}".format(value, multiple_of, title=title)
        )


def validate_is_boolean(value: bool, title: str="Value") -> None:
    if not isinstance(value, bool):
        raise ValidationError(
            "{title} must be an boolean.  Got type: {0}".format(type(value), title=title)
        )


def validate_word(value: Hash32, title: str="Value") -> None:
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


def validate_uint256(value: int, title: str="Value") -> None:
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


def validate_stack_int(value: int) -> None:
    if 0 <= value <= UINT_256_MAX:
        return
    raise ValidationError(
        "Invalid Stack Item: Must be either a length 32 byte "
        "string or a 256 bit integer. Got {!r}".format(value)
    )


def validate_stack_bytes(value: bytes) -> None:
    if len(value) <= 32:
        return
    raise ValidationError(
        "Invalid Stack Item: Must be either a length 32 byte "
        "string or a 256 bit integer. Got {!r}".format(value)
    )


validate_lt_secpk1n = functools.partial(validate_lte, maximum=SECPK1_N - 1)
validate_lt_secpk1n2 = functools.partial(validate_lte, maximum=SECPK1_N // 2 - 1)


def validate_unique(values: Iterable[Any], title: str="Value") -> None:
    if not itertoolz.isdistinct(values):
        duplicates = functoolz.pipe(
            values,
            itertoolz.frequencies,  # get the frequencies

            # filter to ones that occure > 1
            functoolz.partial(dicttoolz.valfilter, lambda v: v > 1),
            sorted,  # sort them
            tuple,  # cast them to an immutiable form
        )
        raise ValidationError(
            "{title} does not contain unique items.  Duplicates: {0}".format(
                ', '.join((str(value) for value in duplicates)),
                title=title,
            )
        )


def validate_block_number(block_number: int, title: str="Block Number") -> None:
    validate_is_integer(block_number, title)
    validate_gte(block_number, 0, title)


def validate_vm_block_numbers(vm_block_numbers: Iterable[int]) -> None:
    validate_unique(vm_block_numbers, title="Block Number set")

    for block_number in vm_block_numbers:
        validate_block_number(block_number)


def validate_vm_configuration(vm_configuration: Tuple[Tuple[int, Type['BaseVM']], ...]) -> None:
    validate_vm_block_numbers(tuple(
        block_number
        for block_number, _
        in vm_configuration
    ))


def validate_gas_limit(gas_limit: int, parent_gas_limit: int) -> None:
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


def validate_header_params_for_configuration(header_params: Dict[str, Any]) -> None:
    extra_fields = set(header_params.keys()).difference(ALLOWED_HEADER_FIELDS)
    if extra_fields:
        raise ValidationError(
            "The `configure_header` method may only be used with the fields ({0}). "
            "The provided fields ({1}) are not supported".format(
                ", ".join(tuple(sorted(ALLOWED_HEADER_FIELDS))),
                ", ".join(tuple(sorted(extra_fields))),
            )
        )
