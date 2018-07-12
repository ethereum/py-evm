import pytest

from eth.vm.stack import (
    Stack,
)
from eth.exceptions import (
    FullStack,
    InsufficientStack,
    ValidationError,
)
from eth.constants import (
    UINT256,
    BYTES,
    SECPK1_N,
)


@pytest.fixture
def stack():
    return Stack()


@pytest.mark.parametrize(
    ("value,is_valid"),
    (
        (-1, False),
        (0, True),
        (1, True),
        (2**256 - 1, True),
        (2**256, False),
        ('abcde', False),
        (b'abcde', True),
        (b'100100100100100100100100100100100', False),
    )
)
def test_push_only_pushes_valid_stack_items(stack, value, is_valid):
    if is_valid:
        stack.push(value)
        assert stack.values == [value]
    else:
        with pytest.raises(ValidationError):
            stack.push(value)


def test_push_does_not_allow_stack_to_exceed_1024_items(stack):
    for num in range(1024):
        stack.push(num)
    assert len(stack.values) == 1024
    with pytest.raises(FullStack):
        stack.push(1025)


def test_dup_does_not_allow_stack_to_exceed_1024_items(stack):
    stack.push(1)
    for num in range(1023):
        stack.dup(1)
    assert len(stack.values) == 1024
    with pytest.raises(FullStack):
        stack.dup(1)


@pytest.mark.parametrize(
    ("items,type_hint"),
    (
        ([1], UINT256),
        ([1, 2, 3], UINT256),
        ([b'1', b'10', b'101', b'1010'], BYTES)
    )
)
def test_pop_returns_latest_stack_item(stack, items, type_hint):
    for each in items:
        stack.push(each)
    assert stack.pop(num_items=1, type_hint=type_hint) == items[-1]


@pytest.mark.parametrize(
    ("value,type_hint,type,is_valid"),
    (
        (1, UINT256, int, True),
        (b'101', BYTES, bytes, True),
        (1, SECPK1_N, int, False)
    )
)
def test_pop_typecasts_correctly_based_off_type_hint(stack, value, type_hint, type, is_valid):
    stack.push(value)
    if is_valid:
        assert isinstance(stack.pop(num_items=1, type_hint=type_hint), type)
    else:
        with pytest.raises(TypeError):
            stack.pop(type_hint=type_hint)


def test_swap_operates_correctly(stack):
    for num in range(5):
        stack.push(num)
    assert stack.values == [0, 1, 2, 3, 4]
    stack.swap(3)
    assert stack.values == [0, 4, 2, 3, 1]
    stack.swap(1)
    assert stack.values == [0, 4, 2, 1, 3]


def test_dup_operates_correctly(stack):
    for num in range(5):
        stack.push(num)
    assert stack.values == [0, 1, 2, 3, 4]
    stack.dup(1)
    assert stack.values == [0, 1, 2, 3, 4, 4]
    stack.dup(5)
    assert stack.values == [0, 1, 2, 3, 4, 4, 1]


def test_pop_raises_InsufficientStack_appropriately(stack):
    with pytest.raises(InsufficientStack):
        stack.pop(num_items=1, type_hint=UINT256)


def test_swap_raises_InsufficientStack_appropriately(stack):
    with pytest.raises(InsufficientStack):
        stack.swap(0)


def test_dup_raises_InsufficientStack_appropriately(stack):
    with pytest.raises(InsufficientStack):
        stack.dup(0)
