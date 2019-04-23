import copy

import pytest

from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.tracking.connection import (
    get_timeout_for_failure,
    register_error,
)


@pytest.fixture(autouse=True)
def _prevent_global_mutation_of_registry(monkeypatch):
    # Ensure that the tests don't result in mutation of the configuration of
    # timeout failures.
    from p2p.tracking import connection
    original = copy.copy(connection.FAILURE_TIMEOUTS)
    yield
    keys_to_pop = set(connection.FAILURE_TIMEOUTS.keys()).difference(original.keys())
    for key in keys_to_pop:
        connection.FAILURE_TIMEOUTS.pop(key)
    for key, value in original.items():
        connection.FAILURE_TIMEOUTS[key] = value


def test_get_timeout_for_failure_with_HandshakeFailure():
    assert get_timeout_for_failure(HandshakeFailure()) == 10


def test_get_timeout_for_failure_with_unknown_exception():
    class UnknownException(Exception):
        pass

    with pytest.raises(Exception, match="Unknown failure type"):
        get_timeout_for_failure(UnknownException())


def test_get_timeout_for_failure_with_3rd_party_exception():
    class UnknownException(Exception):
        pass

    # verify it isn't yet registered
    with pytest.raises(Exception, match="Unknown failure type"):
        get_timeout_for_failure(UnknownException())

    register_error(UnknownException, 1234)

    assert get_timeout_for_failure(UnknownException()) == 1234
