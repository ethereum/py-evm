import os
import pytest

from trinity.utils.filesystem import is_same_path


@pytest.mark.parametrize(
    'path_a,path_b,expected',
    (
        # same paths
        ('path-a', 'path-a', True),
        ('path-a', 'path-a/', True),
        ('path-a', 'path-a/.', True),
        ('path-a', 'path-a/sub-path/..', True),
        ('path-a', 'path-a/sub-path/../', True),
        ('path-a', 'path-a/sub-path/../.', True),
        # different paths
        ('path-a', 'path-b', False),
        ('path-a', 'path-b/', False),
        ('path-a', 'path-b/.', False),
        ('path-a/', 'path-b', False),
        ('path-a/.', 'path-b', False),
        # rel vs abs paths
        ('path-a', os.path.abspath('path-a'), True),
        # both abs
        ('/path-a/sub-path', '/path-a/sub-path', True),
        ('/path-a/sub-path', '/path-a/sub-path/', True),
        ('/path-a/sub-path', '/path-a/sub-path/.', True),
    )
)
@pytest.mark.parametrize('invert', (True, False))
def test_is_same_path(path_a, path_b, expected, invert):
    if invert:
        actual = is_same_path(path_b, path_a)
    else:
        actual = is_same_path(path_a, path_b)

    assert actual is expected
