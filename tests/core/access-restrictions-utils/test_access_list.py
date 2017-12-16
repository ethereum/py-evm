import pytest

import rlp
from rlp.exceptions import (
    ListSerializationError,
    ListDeserializationError,
)

from evm.constants import (
    STORAGE_TRIE_PREFIX,
)
from evm.validation import (
    validate_transaction_access_list,
)

from evm.rlp.sedes import (
    access_list as access_list_sedes,
)
from evm.utils.keccak import (
    keccak,
)
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
    assert len(slot) == 32
    key = keccak(address) + STORAGE_TRIE_PREFIX + slot
    if accessible:
        assert is_accessible(key, prefix_list)
    else:
        assert not is_accessible(key, prefix_list)


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


@pytest.mark.parametrize(
    'access_list,expected',
    [
        (
            (),
            b'\xc0'
        ),
        (
            ((TEST_ADDRESS1,),),
            b'\xd6' + b'\xd5' + b'\x94' + TEST_ADDRESS1
        ),
        (
            ((TEST_ADDRESS1, b''),),
            b'\xd7' + b'\xd6' + b'\x94' + TEST_ADDRESS1 + b'\x80'
        ),
        (
            ((TEST_ADDRESS1, b'\xaa'),),
            b'\xd8' + b'\xd7' + b'\x94' + TEST_ADDRESS1 + b'\x81\xaa'
        ),
        (
            ((TEST_ADDRESS1, b'\xaa' * 32),),
            b'\xf7' + b'\xf6' + b'\x94' + TEST_ADDRESS1 + b'\xa0' + b'\xaa' * 32
        ),
        (
            (
                (TEST_ADDRESS1, b'\xaa' * 20, b'\xbb' * 2, b'\xcc' * 32),
                (TEST_ADDRESS2, b'\xaa\xbb')
            ),
            b'\xf8\x69' + (
                b'\xf8\x4e' + (
                    b'\x94' + TEST_ADDRESS1 +
                    b'\x94' + b'\xaa' * 20 +
                    b'\x82\xbb\xbb' +
                    b'\xa0' + b'\xcc' * 32
                ) +
                b'\xd8' + (
                    b'\x94' + TEST_ADDRESS2 +
                    b'\x82\xaa\xbb'
                )
            )
        ),
    ]
)
def test_rlp_encoding(access_list, expected):
    validate_transaction_access_list(access_list)
    encoded = rlp.encode(access_list, access_list_sedes)
    print(encoded)
    print(expected)
    assert encoded == expected

    decoded = rlp.decode(encoded, access_list_sedes)
    assert decoded == access_list


@pytest.mark.parametrize(
    'invalid_access_list',
    [
        b'',
        [[]],
        [[[]]],
        [[b'']],
        [[b'\xaa' * 40]],
        [[b'\xaa' * 19]],
        [[b'\xaa' * 21]],
        [[b'\xaa' * 32]],
        [[b'\xaa' * 20, b'\xaa' * 33]],
        [[], [b'\xaa']],
    ]
)
def test_invalid_rlp_encoding(invalid_access_list):
    with pytest.raises(ListSerializationError):
        rlp.encode(invalid_access_list, access_list_sedes)

    encoded = rlp.encode(invalid_access_list)
    with pytest.raises(ListDeserializationError):
        rlp.decode(encoded, access_list_sedes)
