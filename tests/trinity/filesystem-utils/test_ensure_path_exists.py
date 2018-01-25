import os

import pytest

from trinity.utils.filesystem import (
    ensure_path_exists,
)


@pytest.mark.parametrize(
    'path',
    (
        os.path.join('one'),
        os.path.join('one', 'two'),
        os.path.join('one', 'two', 'tree'),
        os.path.join('exists-one'),
        os.path.join('exists-one', 'two'),
        os.path.join('exists-one', 'exists-two'),
        os.path.join('exists-one', 'exists-two', 'three'),
    ),
)
def test_ensure_path_exists_for_existing_dir(tmpdir, path):
    base_path = str(tmpdir.mkdir('test-ensure_path_exists'))
    # setup existing dirs

    full_path = os.path.join(base_path, path)
    ensure_path_exists(full_path)

    assert os.path.exists(full_path)
