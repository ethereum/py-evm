import pytest

from trinity.cli import console


@pytest.fixture
def chain():
    # Attach a dummy run method to chain fixture as console method needs it.
    from tests.core.fixtures import chain

    async def run():
        pass
    # Setup
    chain.run = run
    yield chain
    # Teardown
    del chain.run


def test_console(chain):
    # Test running the console, actually start it.
    with pytest.raises(OSError, match='^reading .* stdin .* captured$'):
        console(chain)


def test_python_console(chain):
    # Test running the default python REPL, actually start it.
    with pytest.raises(OSError, match='^reading .* stdin .* captured$'):
        console(chain, use_ipython=False)
