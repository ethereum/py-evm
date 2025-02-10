import pytest

from eth_utils import (
    ValidationError,
)

from eth.abc import (
    AtomicDatabaseAPI,
)


class AtomicDatabaseBatchAPITestSuite:
    def test_atomic_batch_set_and_get(self, atomic_db: AtomicDatabaseAPI) -> None:
        with atomic_db.atomic_batch() as batch:
            batch.set(b"1", b"2")
            assert batch.get(b"1") == b"2"

        assert atomic_db.get(b"1") == b"2"

    def test_atomic_db_cannot_recursively_batch(
        self, atomic_db: AtomicDatabaseAPI
    ) -> None:
        with atomic_db.atomic_batch() as batch:
            assert not hasattr(batch, "atomic_batch")

    def test_atomic_db_with_set_and_delete_batch(
        self, atomic_db: AtomicDatabaseAPI
    ) -> None:
        atomic_db[b"key-1"] = b"origin"

        with atomic_db.atomic_batch() as batch:
            batch.delete(b"key-1")

            assert b"key-1" not in batch
            with pytest.raises(KeyError):
                assert batch[b"key-1"]

        with pytest.raises(KeyError):
            atomic_db[b"key-1"]

    def test_atomic_db_unbatched_sets_are_immediate(
        self, atomic_db: AtomicDatabaseAPI
    ) -> None:
        atomic_db[b"1"] = b"A"

        with atomic_db.atomic_batch() as batch:
            # Unbatched changes are immediate, and show up in batch reads
            atomic_db[b"1"] = b"B"
            assert batch[b"1"] == b"B"

            batch[b"1"] = b"C1"

            # It doesn't matter what changes happen underlying, all reads now
            # show the write applied to the batch db handle
            atomic_db[b"1"] = b"C2"
            assert batch[b"1"] == b"C1"

        # the batch write should overwrite any intermediate changes
        assert atomic_db[b"1"] == b"C1"

    def test_atomic_db_unbatched_deletes_are_immediate(
        self, atomic_db: AtomicDatabaseAPI
    ) -> None:
        atomic_db[b"1"] = b"A"

        with atomic_db.atomic_batch() as batch:
            assert b"1" in batch

            # Unbatched changes are immediate, and show up in batch reads
            del atomic_db[b"1"]

            assert b"1" not in batch

            batch[b"1"] = b"C1"

            # It doesn't matter what changes happen underlying, all reads now
            # show the write applied to the batch db handle
            atomic_db[b"1"] = b"C2"
            assert batch[b"1"] == b"C1"

        # the batch write should overwrite any intermediate changes
        assert atomic_db[b"1"] == b"C1"

    def test_atomic_db_cannot_use_batch_after_context(
        self, atomic_db: AtomicDatabaseAPI
    ) -> None:
        atomic_db[b"1"] = b"A"

        with atomic_db.atomic_batch() as batch:
            batch[b"1"] = b"B"

        # set
        with pytest.raises(ValidationError):
            batch[b"1"] = b"C"

        with pytest.raises(ValidationError):
            batch.set(b"1", b"C")

        # get
        with pytest.raises(ValidationError):
            batch[b"1"]

        with pytest.raises(ValidationError):
            batch.get(b"1")

        # exists
        with pytest.raises(ValidationError):
            assert b"1" in batch

        with pytest.raises(ValidationError):
            batch.exists(b"1")

        # delete
        with pytest.raises(ValidationError):
            del batch[b"1"]

        with pytest.raises(ValidationError):
            batch.delete(b"1")

        # none of the invalid changes above should change the original db
        assert atomic_db[b"1"] == b"B"

    def test_atomic_db_with_reverted_delete_batch(
        self, atomic_db: AtomicDatabaseAPI
    ) -> None:
        class CustomException(Exception):
            pass

        atomic_db[b"key-1"] = b"origin"

        with pytest.raises(CustomException):
            with atomic_db.atomic_batch() as batch:
                batch.delete(b"key-1")

                assert b"key-1" not in batch
                with pytest.raises(KeyError):
                    assert batch[b"key-1"]

                raise CustomException("pretend something went wrong")

        assert atomic_db[b"key-1"] == b"origin"

    def test_atomic_db_temporary_state_dropped_across_batches(
        self, atomic_db: AtomicDatabaseAPI
    ) -> None:
        class CustomException(Exception):
            pass

        atomic_db[b"key-1"] = b"origin"

        with pytest.raises(CustomException):
            with atomic_db.atomic_batch() as batch:
                batch.delete(b"key-1")
                batch.set(b"key-2", b"val-2")
                raise CustomException("pretend something went wrong")

        with atomic_db.atomic_batch() as batch:
            assert batch[b"key-1"] == b"origin"
            assert b"key-2" not in batch

    def test_atomic_db_with_exception_batch(self, atomic_db: AtomicDatabaseAPI) -> None:
        atomic_db.set(b"key-1", b"value-1")

        try:
            with atomic_db.atomic_batch() as batch:
                batch.set(b"key-1", b"new-value-1")
                batch.set(b"key-2", b"value-2")
                raise Exception
        except Exception:
            pass

        assert atomic_db.get(b"key-1") == b"value-1"

        with pytest.raises(KeyError):
            atomic_db[b"key-2"]
