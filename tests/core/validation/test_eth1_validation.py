from eth_utils import (
    ValidationError,
)
import pytest

from eth.constants import (
    SECPK1_N,
)
from eth.validation import (
    validate_block_number,
    validate_canonical_address,
    validate_gt,
    validate_gte,
    validate_is_boolean,
    validate_is_bytes,
    validate_is_integer,
    validate_is_list_like,
    validate_is_transaction_access_list,
    validate_length,
    validate_length_lte,
    validate_lt,
    validate_lt_secpk1n,
    validate_lt_secpk1n2,
    validate_lte,
    validate_multiple_of,
    validate_stack_bytes,
    validate_stack_int,
    validate_uint256,
    validate_unique,
    validate_vm_block_numbers,
    validate_vm_configuration,
    validate_word,
)

byte = b"\x00"


@pytest.mark.parametrize(
    "value,is_valid",
    (
        ((), True),
        ([], True),
        ({}, True),
        (set(), True),
        ([1, 2, 3], True),
        ([1, 2, 1], False),
        (["a", "b", "c"], True),
        (["1", "2", "3"], True),
        (["1", "2", "1"], False),
        (["1", "2", 1], True),
    ),
)
def test_validate_unique(value, is_valid):
    if is_valid:
        validate_unique(value)
    else:
        with pytest.raises(ValidationError):
            validate_unique(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        ((), False),
        ([], False),
        ({}, False),
        (set(), False),
        (1, False),
        (True, False),
        ("abc", False),
        (b"abc", True),
    ),
)
def test_validate_is_bytes(value, is_valid):
    if is_valid:
        validate_is_bytes(value)
    else:
        with pytest.raises(ValidationError):
            validate_is_bytes(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        ((), False),
        ([], False),
        ({}, False),
        (set(), False),
        (1234, True),
        ("abc", False),
        (True, False),
    ),
)
def test_validate_is_integer(value, is_valid):
    if is_valid:
        validate_is_integer(value)
    else:
        with pytest.raises(ValidationError):
            validate_is_integer(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        ((), False),
        ([], False),
        ({}, False),
        (set(), False),
        ("a", False),
        (1, False),
        (True, True),
        (False, True),
    ),
)
def test_validate_is_boolean(value, is_valid):
    if is_valid:
        validate_is_boolean(value)
    else:
        with pytest.raises(ValidationError):
            validate_is_boolean(value)


@pytest.mark.parametrize(
    "value,length,is_valid",
    (
        ((), 0, True),
        ([1], 1, True),
        ({"A": "B", "C": 1}, 3, False),
        ({"A", "B", 1, 2}, 4, True),
        ("abcde", 4, False),
        (b"123", 3, True),
        (range(1, 10), 9, True),
    ),
)
def test_validate_length(value, length, is_valid):
    if is_valid:
        validate_length(value, length)
    else:
        with pytest.raises(ValidationError):
            validate_length(value, length)


@pytest.mark.parametrize(
    "value,maximum_length,is_valid",
    (
        ((), 0, True),
        ([1], 0, False),
        ({"A": "B", "C": 1}, 3, True),
        ({"A", "B", 1, 2}, 2, False),
        ("abcde", 5, True),
        (b"123", 3, True),
        (range(1, 10), 15, True),
    ),
)
def test_validate_length_lte(value, maximum_length, is_valid):
    if is_valid:
        validate_length_lte(value, maximum_length)
    else:
        with pytest.raises(ValidationError):
            validate_length_lte(value, maximum_length)


@pytest.mark.parametrize(
    "value,minimum,is_valid",
    (
        (1, 2, False),
        (1, 1, True),
        ("a", "a", False),
        (3, 2, True),
    ),
)
def test_validate_gte(value, minimum, is_valid):
    if is_valid:
        validate_gte(value, minimum)
    else:
        with pytest.raises(ValidationError):
            validate_gte(value, minimum)


@pytest.mark.parametrize(
    "value,minimum,is_valid",
    (
        (1, 2, False),
        (1, 1, False),
        ("a", "a", False),
        (3, 2, True),
    ),
)
def test_validate_gt(value, minimum, is_valid):
    if is_valid:
        validate_gt(value, minimum)
    else:
        with pytest.raises(ValidationError):
            validate_gt(value, minimum)


@pytest.mark.parametrize(
    "value,maximum,is_valid",
    (
        (1, 2, True),
        (1, 1, True),
        ("a", "a", False),
        (3, 2, False),
    ),
)
def test_validate_lte(value, maximum, is_valid):
    if is_valid:
        validate_lte(value, maximum)
    else:
        with pytest.raises(ValidationError):
            validate_lte(value, maximum)


@pytest.mark.parametrize(
    "value,maximum,is_valid",
    (
        (1, 2, True),
        (1, 1, False),
        ("a", "a", False),
        (3, 2, False),
    ),
)
def test_validate_lt(value, maximum, is_valid):
    if is_valid:
        validate_lt(value, maximum)
    else:
        with pytest.raises(ValidationError):
            validate_lt(value, maximum)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        ("10010010010010010010", False),
        (b"10010010010010010010", True),
        (b"abc", False),
        (b"12345", False),
    ),
)
def test_validate_canonical_address(value, is_valid):
    if is_valid:
        validate_canonical_address(value)
    else:
        with pytest.raises(ValidationError):
            validate_canonical_address(value)


@pytest.mark.parametrize(
    "value,multiple_of,is_valid",
    (
        (1, 1, True),
        (4, 2, True),
        (773, 3, False),
    ),
)
def test_validate_multiple_of(value, multiple_of, is_valid):
    if is_valid:
        validate_multiple_of(value, multiple_of)
    else:
        with pytest.raises(ValidationError):
            validate_multiple_of(value, multiple_of)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        (1, False),
        ("word", False),
        (b"word", False),
        (b"10010010010010010010010010010010", True),
    ),
)
def test_validate_word(value, is_valid):
    if is_valid:
        validate_word(value)
    else:
        with pytest.raises(ValidationError):
            validate_word(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        ((), False),
        ("a", False),
        (-1, False),
        (0, True),
        (1, True),
        (2**256, False),
        ((2**256) - 1, True),
    ),
)
def test_validate_uint256(value, is_valid):
    if is_valid:
        validate_uint256(value)
    else:
        with pytest.raises(ValidationError):
            validate_uint256(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        (-1, False),
        (0, True),
        (10, True),
        (2**256, False),
        ((2**256) - 1, True),
    ),
)
def test_validate_stack_int(value, is_valid):
    if is_valid:
        validate_stack_int(value)
    else:
        with pytest.raises(ValidationError):
            validate_stack_int(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        (b"", True),
        (b"a", True),
        (b"10010010010010010010010010010010", True),
        (b"100100100100100100100100100100100", False),
    ),
)
def test_validate_stack_bytes(value, is_valid):
    if is_valid:
        validate_stack_bytes(value)
    else:
        with pytest.raises(ValidationError):
            validate_stack_bytes(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        ([], True),
        (["list", "of", 4, "items"], True),
        (["list", "of", "just", "strings"], True),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], True),
        ([1], True),
        ((), True),
        (("tuple", "of", 4, "items"), True),
        (("tuple", "of", "just", "strings"), True),
        ((1, 2, 3, 4, 5, 6, 7, 8, 9, 0), True),
        ((1,), True),
        ({"set", "of", 4, "items"}, False),
        ({"set", "of", "just", "strings"}, False),
        ({1, 2, 3, 4, 5, 6, 7, 8, 9, 0}, False),
        ({1}, False),
        ({"dict": 0, "of": "items"}, False),
        (b"", False),
        (b"a", False),
        (b"101010", False),
        (b"\xfd\xf2\xfc", False),
        ("", False),
        ("string", False),
        ("1", False),
        ("", False),
        ("unicode string", False),
        (1, False),
        (1.1, False),
    ),
)
def test_validate_is_list_like(value, is_valid):
    if is_valid:
        # True for tuples and lists
        validate_is_list_like(value)
    else:
        with pytest.raises(ValidationError):
            validate_is_list_like(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        (((b"\xf0" * 20, (1,)),), True),
        ([[b"\xf0" * 20, [1]]], True),
        (((b"\xf0" * 20, (0, 2)),), True),
        (((b"\xef" * 20, (1, 2, 3)),), True),
        (
            (
                (b"\xf0" * 20, (1, 2, 3)),
                (b"\xef" * 20, ()),
            ),
            True,
        ),
        (((b"\xf0" * 20, ()),), True),
        ((), True),
        ([], True),
        (((b"\xf0" * 19, (0, 2)),), False),
        ((("\xf0" * 20, (0, 2)),), False),
        (((b"", (0, 2)),), False),
        (((b"\xf0" * 20, (0, "2")),), False),
        (((b"\xf0" * 20, (0, b"\xf0")),), False),
        (((b"\xf0" * 20, (0, (1, 2))),), False),
        (((b"\xf0" * 20,),), False),  # just one value in entry, an address
        ((((1, 2),),), False),  # just one value in entry, a list of valid storage keys
    ),
)
def test_validate_is_transaction_access_list(value, is_valid):
    if is_valid:
        validate_is_transaction_access_list(value)
    else:
        with pytest.raises(ValidationError):
            validate_is_transaction_access_list(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        (-1, True),
        (0, True),
        (1, True),
        (SECPK1_N - 1, True),
        (SECPK1_N, False),
    ),
)
def test_validate_lt_secpk1n(value, is_valid):
    if is_valid:
        validate_lt_secpk1n(value)
    else:
        with pytest.raises(ValidationError):
            validate_lt_secpk1n(value)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        (-1, True),
        (0, True),
        (1, True),
        (SECPK1_N // 2 - 1, True),
        (SECPK1_N // 2, False),
    ),
)
def test_validate_lt_secpk1n2(value, is_valid):
    if is_valid:
        validate_lt_secpk1n2(value)
    else:
        with pytest.raises(ValidationError):
            validate_lt_secpk1n2(value)


@pytest.mark.parametrize(
    "block_number,is_valid",
    (
        ((), False),
        ([], False),
        ({}, False),
        (set(), False),
        ("abc", False),
        (1234, True),
        (-1, False),
        (0, True),
        (100, True),
    ),
)
def test_validate_block_number(block_number, is_valid):
    if is_valid:
        validate_block_number(block_number)
    else:
        with pytest.raises(ValidationError):
            validate_block_number(block_number)


@pytest.mark.parametrize(
    "vm_block_numbers,is_valid",
    (
        ([], True),
        ([1], True),
        ([1, 2, 3], True),
        ([1, 2, 1], False),
        (["a", "b", "c"], False),
        (["1", "2", "1"], False),
        (["1", "2", 1], False),
    ),
)
def test_validate_vm_block_numbers(vm_block_numbers, is_valid):
    if is_valid:
        validate_vm_block_numbers(vm_block_numbers)
    else:
        with pytest.raises(ValidationError):
            validate_vm_block_numbers(vm_block_numbers)


@pytest.mark.parametrize(
    "value",
    (
        ((-1, None),),  # negative block number
        ((0, None), (0, None)),  # duplicate number
    ),
)
def test_validate_vm_configuration_bad_configs(value):
    with pytest.raises(ValidationError):
        validate_vm_configuration(value)
