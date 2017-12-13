import pytest

from evm.utils.state_access_restriction import (
    is_accessible,
    remove_redundant_prefixes,
    to_prefix_list_form,
)


TEST_ADDRESS1 = b'\xaa' * 20
TEST_ADDRESS2 = b'\xbb' * 20
TEST_PREFIX_LIST = to_prefix_list_form([
    [TEST_ADDRESS1, b'\x00'],
    [TEST_ADDRESS1, b'\x01\x00'],
    [TEST_ADDRESS2, b'\xff' * 32]
])


@pytest.mark.parametrize(
    "prefix_list,address,slot,accessible",
    (
        [[], TEST_ADDRESS1, b'\x00' * 32, False],
        [TEST_PREFIX_LIST, TEST_ADDRESS1, b'\x00' * 32, True],
        [TEST_PREFIX_LIST, TEST_ADDRESS1, b'\x00' + b'\xff' * 31, True],
        [TEST_PREFIX_LIST, TEST_ADDRESS1, b'\xff' + b'\x00' * 31, False],
        [TEST_PREFIX_LIST, TEST_ADDRESS1, b'\xff' * 32, False],
        [TEST_PREFIX_LIST, TEST_ADDRESS1, b'\x01\x00' + b'\x00' * 30, True],
        [TEST_PREFIX_LIST, TEST_ADDRESS1, b'\x01\x00' + b'\xff' * 30, True],
        [TEST_PREFIX_LIST, TEST_ADDRESS1, b'\x01\x00' + b'\x00' * 30, True],
        [TEST_PREFIX_LIST, TEST_ADDRESS1, b'\x01\x01' + b'\x00' * 30, False],
        [TEST_PREFIX_LIST, TEST_ADDRESS2, b'\xff' * 32, True],
        [TEST_PREFIX_LIST, TEST_ADDRESS2, b'\xff' * 31 + b'\x00', False],
        [TEST_PREFIX_LIST, TEST_ADDRESS2, b'\x00' + b'\xff' * 31, False],
        [to_prefix_list_form([[TEST_ADDRESS1, b'']]), TEST_ADDRESS1, b'\x00' * 32, True],
    )
)
def test_accessibility(prefix_list, address, slot, accessible):
    if accessible:
        assert is_accessible(address, slot, prefix_list)
    else:
        assert not is_accessible(address, slot, prefix_list)


@pytest.mark.parametrize(
    'prefixes,expected',
    (
        (
            (b'', b'something'),
            {b''},
        ),
        (
            (b'ethereum', b'eth', b'ether', b'england', b'eng'),
            {b'eth', b'eng'},
        ),
        (
            (b'ethereum', b'ethereua'),
            {b'ethereum', b'ethereua'},
        ),
        (
            (b'a', b'aa', b'b', b'bb', b'ab', b'ba'),
            {b'a', b'b'},
        ),
    ),
)
def test_remove_redundant_prefixes(prefixes, expected):
    actual = remove_redundant_prefixes(prefixes)
    assert actual == expected
