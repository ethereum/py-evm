import pytest

from py_ecc import bls


@pytest.fixture(scope="session")
def privkey_count():
    return 100


@pytest.fixture(scope="session")
def privkeys(privkey_count):
    """
    Rationales:
    1. Making the privkeys be small integers to make multiplying easier for tests.
    2. Using ``2**i`` instead of ``i``:
        If using ``i``, the combinations of privkeys would not lead to unique pubkeys.
    """
    return [2 ** i for i in range(privkey_count)]


@pytest.fixture(scope="session")
def keymap(privkeys):
    return {
        bls.privtopub(k): k
        for k in privkeys
    }


@pytest.fixture(scope="session")
def pubkeys(keymap):
    return list(keymap)
