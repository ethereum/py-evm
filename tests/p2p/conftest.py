import pytest


@pytest.fixture(scope='session', autouse=True)
def ensure_pytest_asyncio():
    try:
        import pytest_asyncio  # noqa: F401
    except ModuleNotFoundError:
        raise AssertionError("Missing pytest-asyncio, cannot run asyncio tests")
