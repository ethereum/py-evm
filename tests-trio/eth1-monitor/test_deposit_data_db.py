import pytest

from trinity.components.eth2.eth1_monitor.db import DepositDataDB
from trinity.components.eth2.eth1_monitor.exceptions import (
    DepositDataNotFound,
    DepositDataDBValidationError,
)
from trinity.components.eth2.eth1_monitor.factories import (
    DepositDataDBFactory,
    DepositDataFactory,
)


def test_deposit_data_db():
    db: DepositDataDB = DepositDataDBFactory()
    # Test: Default values
    assert db.deposit_count == 0
    assert db.highest_processed_block_number == 0

    # Test: `DepositDataNotFound` is raised when a `DepositData` at the given `index` is not found.
    with pytest.raises(DepositDataNotFound):
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
        assert db.get_deposit_count() == db.deposit_count
        assert db.get_highest_processed_block_number() == block_number
        block_number += 1
    db.add_deposit_data_batch(sequence_deposit_data[6:], block_number)
    assert db.deposit_count == target_deposit_count
    assert db.get_highest_processed_block_number() == block_number

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
    new_db: DepositDataDB = DepositDataDBFactory(db=db.db)
    for i, data in enumerate(sequence_deposit_data):
        assert new_db.get_deposit_data(i) == data
    assert new_db.deposit_count == db.deposit_count
    assert new_db.highest_processed_block_number == db.highest_processed_block_number
