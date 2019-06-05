import pytest

from eth.db.atomic import AtomicDB

from .integration_fixture_builders import build_pow_fixture, build_pow_churning_fixture


@pytest.mark.parametrize('builder', (build_pow_fixture, build_pow_churning_fixture))
def test_fixture_builders(builder):
    # just make sure it doesn't crash, for now
    db = AtomicDB()
    builder(db, num_blocks=5)


# TODO add a long test that makes sure that we can rebuild the zipped ldb fixtures
#   with the expected state roots. But probably skip during normal CI runs, for speed.
