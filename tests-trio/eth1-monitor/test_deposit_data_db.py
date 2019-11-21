import pytest

from trinity.components.eth2.eth1_monitor.db import (
    BaseDepositDataDB,
    ListCachedDepositDataDB,
)
from trinity.components.eth2.eth1_monitor.exceptions import DepositDataDBValidationError
from trinity.components.eth2.eth1_monitor.factories import (
    DepositDataDBFactory,
    DepositDataFactory,
    ListCachedDepositDataDBFactory,
)
from trinity.tools.factories.db import AtomicDBFactory


@pytest.mark.parametrize(
    "db_factory", (DepositDataDBFactory, ListCachedDepositDataDBFactory)
)
def test_db(db_factory):
    atomic_db = AtomicDBFactory()
    db: BaseDepositDataDB = db_factory(db=atomic_db)
    # Test: Default values
    assert db.deposit_count == 0
    assert db.highest_processed_block_number == 0

    # Test: `DepositDataDBValidationError` is raised when a `DepositData` at the given `index`
    #   is not found.
    with pytest.raises(DepositDataDBValidationError):
        db.get_deposit_data(0)

    # Test: Ensure `add_deposit_data_batch` works and `deposit_count` is updated and saved as well.
    target_deposit_count = 10
    sequence_deposit_data = tuple(
        DepositDataFactory() for _ in range(target_deposit_count)
    )
    block_number = 1
    for i, data in enumerate(sequence_deposit_data[:6]):
        db.add_deposit_data_batch([data], block_number)
        assert db.deposit_count == i + 1
        assert db.highest_processed_block_number == block_number
        block_number += 1
    db.add_deposit_data_batch(sequence_deposit_data[6:], block_number)
    assert db.deposit_count == target_deposit_count
    assert db.highest_processed_block_number == block_number

    # Test: Ensure `highest_processed_block_number` should be only ascending.
    # Here, `DepositDataDBValidationError` is raised since `add_deposit_data_batch` with
    #   the same `block_number` used before.
    with pytest.raises(DepositDataDBValidationError):
        db.add_deposit_data_batch([DepositDataFactory()], block_number)

    # Test: Ensure `get_deposit_data` works.
    for i, data in enumerate(sequence_deposit_data):
        assert db.get_deposit_data(i) == data

    # Test: Range access
    for i, _ in enumerate(sequence_deposit_data):
        assert sequence_deposit_data[i:] == db.get_deposit_data_range(
            i, db.deposit_count
        )
        upper_index = i + 1
        assert sequence_deposit_data[0:upper_index] == db.get_deposit_data_range(
            0, upper_index
        )

    # Test: Data is persisted in `DepositDataDB.db`, and can be retrieved when
    #   a new `DepositDataDB` instance takes the same `AtomicDB`.
    new_db: BaseDepositDataDB = db_factory(db=atomic_db)
    for i, data in enumerate(sequence_deposit_data):
        assert new_db.get_deposit_data(i) == data
    assert new_db.deposit_count == db.deposit_count
    assert new_db.highest_processed_block_number == db.highest_processed_block_number


def test_list_cached_deposit_db_cache():
    atomic_db = AtomicDBFactory()
    cached_db: ListCachedDepositDataDB = ListCachedDepositDataDBFactory(db=atomic_db)
    deposit_data_db = cached_db._db

    # Test: Data is cached in the internal list
    data = DepositDataFactory()
    cached_db.add_deposit_data_batch([data], 1)
    assert data in cached_db._cache_deposit_data
    assert deposit_data_db.get_deposit_data(0) == data
    assert cached_db.get_deposit_data(0) == data
    assert cached_db.deposit_count == 1

    # Test: Data is persisted in `AtomicDB`. `ListCachedDepositDataDB` can parse the data inside
    #   and set up the cache properly.
    another_cached_db = ListCachedDepositDataDBFactory(db=atomic_db)
    assert another_cached_db.deposit_count == cached_db.deposit_count
    assert (
        another_cached_db.highest_processed_block_number
        == cached_db.highest_processed_block_number  # noqa: W503
    )
    assert cached_db._cache_deposit_data == another_cached_db._cache_deposit_data
