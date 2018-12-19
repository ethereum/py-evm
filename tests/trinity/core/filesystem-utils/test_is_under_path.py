import pytest

from trinity._utils.filesystem import (
    is_under_path,
)


@pytest.mark.parametrize(
    'base_path,path,expected',
    (
        # Same Path
        ('foo', 'foo', False),
        ('foo', 'foo/bar/..', False),
        # up a directory (or two)
        ('foo', '..', False),
        ('foo', 'foo/bar/../../', False),
        # relative and abs
        ('foo', '/foo/bar', False),
        ('foo', '/foo', False),
        # actually nested
        ('foo', 'foo/bar.sol', True),
        ('foo', 'foo/bar', True),
        ('foo', 'foo/bar/../../foo/baz', True),
    ),
)
def test_is_under_path(base_path, path, expected):
    actual = is_under_path(base_path, path)
    assert actual is expected
