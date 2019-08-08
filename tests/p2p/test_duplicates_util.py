import pytest

from p2p._utils import duplicates


@pytest.mark.parametrize(
    'elements,expected',
    (
        ((), ()),
        ((1,), ()),
        ((1, 2), ()),
        ((2, 1, 2), (2,)),
        ((2, 1, 2, 4, 3, 4), (2, 4)),
        ([], ()),
        ([1], ()),
        ([1, 2], ()),
        ([2, 1, 2], (2,)),
        ([2, 1, 2, 3, 4, 3], (2, 3)),
    ),
)
def test_duplicates_with_identity_fn(elements, expected):
    dups = duplicates(elements)
    assert dups == expected
