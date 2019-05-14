import pytest

from py_ecc import bls


@pytest.fixture(scope="session")
def privkeys():
    """
    Rationales:
    1. Making the privkeys be small integers to make multiplying easier for tests.
    2. Using ``2**i`` instead of ``i``:
        If using ``i``, the combinations of privkeys would not lead to unique pubkeys.
    """
    return [2 ** i for i in range(100)]


@pytest.fixture(scope="session")
def keymap(privkeys):
    keymap = {}
    for i, k in enumerate(privkeys):
        keymap[bls.privtopub(k)] = k
        if i % 50 == 0:
            print("Generated %d keys" % i)
    return keymap


@pytest.fixture(scope="session")
def pubkeys(keymap):
    return list(keymap)
