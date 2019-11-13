import pytest

from trinity.components.eth2.eth1_monitor.db import DepositDataDB
from trinity.components.eth2.eth1_monitor.exceptions import DepositDataNotFound
from trinity.components.eth2.eth1_monitor.factories import (
    DepositDataDBFactory,
    DepositDataFactory,
)


def test_deposit_data_db():
    db: DepositDataDB = DepositDataDBFactory()
    # Test: Initial `deposit_count == 0`.
    assert db.deposit_count == 0

    # Test: `DepositDataNotFound` is raised when a `DepositData` at the given `index` is not found.
    with pytest.raises(DepositDataNotFound):
        db.get_deposit_data(0)

    # Test: Ensure `add_deposit_data` works and `deposit_count` is updated and saved as well.
    target_deposit_count = 5
    sequence_deposit_data = tuple(
        DepositDataFactory() for _ in range(target_deposit_count)
    )
    for i, data in enumerate(sequence_deposit_data):
        db.add_deposit_data(data)
        assert db.deposit_count == i + 1
        assert db.get_deposit_count() == db.deposit_count

    # Test: Ensure `get_deposit_data` works.
    for i, data in enumerate(sequence_deposit_data):
        assert db.get_deposit_data(i) == data

    # Test: Data is persisted in `DepositDataDB.db`, and can be retrieved when
    #   a new `DepositDataDB` instance takes the same `AtomicDB`.
    new_db: DepositDataDB = DepositDataDBFactory(db=db.db)
    for i, data in enumerate(sequence_deposit_data):
        assert new_db.get_deposit_data(i) == data
