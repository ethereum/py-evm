from abc import ABC, abstractmethod

from typing import Tuple

import ssz

from eth.abc import AtomicDatabaseAPI, DatabaseAPI

from eth2.beacon.types.deposit_data import DepositData

from .exceptions import DepositDataNotFound, DepositDataDBValidationError


class BaseSchema(ABC):
    @staticmethod
    @abstractmethod
    def make_deposit_data_lookup_key(index: int) -> bytes:
        ...

    @staticmethod
    @abstractmethod
    def make_deposit_data_count_lookup_key() -> bytes:
        ...


class SchemaV1(BaseSchema):
    @staticmethod
    def make_deposit_data_lookup_key(index: int) -> bytes:
        index_in_str = str(index)
        return b"v1:deposit_data:" + index_in_str.encode()

    @staticmethod
    def make_deposit_data_count_lookup_key() -> bytes:
        return b"v1:deposit_data:count"


class BaseDepositDataDB(ABC):
    @property
    @abstractmethod
    def deposit_count(self) -> int:
        ...

    @abstractmethod
    def add_deposit_data(self, deposit_data: DepositData) -> None:
        ...

    @abstractmethod
    def get_deposit_data(self, index: int) -> DepositData:
        ...

    @abstractmethod
    def get_deposit_data_range(
        self, from_index: int, to_index: int
    ) -> Tuple[DepositData, ...]:
        ...

    @abstractmethod
    def get_deposit_count(self) -> int:
        ...


class DepositDataDB(BaseDepositDataDB):
    db: AtomicDatabaseAPI

    _deposit_count: int

    def __init__(self, db: AtomicDatabaseAPI) -> None:
        self.db = db
        self._deposit_count = self.get_deposit_count()

    @property
    def deposit_count(self) -> int:
        return self._deposit_count

    def add_deposit_data(self, deposit_data: DepositData) -> None:
        count = self.deposit_count
        new_count = count + 1
        with self.db.atomic_batch() as db:
            self._set_deposit_data(db, count, deposit_data)
            self._set_deposit_count(db, new_count)
        self._deposit_count = new_count

    def get_deposit_data(self, index: int) -> DepositData:
        key = SchemaV1.make_deposit_data_lookup_key(index)
        try:
            raw_bytes = self.db[key]
        except KeyError:
            raise DepositDataNotFound(f"`DepositData` at index={index} is not found")
        return ssz.decode(raw_bytes, DepositData)

    def get_deposit_data_range(
        self, from_index: int, to_index: int
    ) -> Tuple[DepositData, ...]:
        if (from_index < 0) or (to_index < 0):
            raise DepositDataDBValidationError(
                "both `from_index` and `to_index` should be non-negative: "
                f"from_index={from_index}, to_index={to_index}"
            )
        if from_index >= to_index:
            raise DepositDataDBValidationError(
                "`to_index` should be larger than `from_index`: "
                f"from_index={from_index}, to_index={to_index}"
            )
        if (from_index >= self.deposit_count) or (to_index > self.deposit_count):
            raise DepositDataDBValidationError(
                "either `from_index` or `to_index` is larger or equaled to `self.deposit_count`: "
                f"from_index={from_index}, to_index={to_index}, "
                f"self.deposit_count={self.deposit_count}"
            )
        return tuple(
            self.get_deposit_data(index) for index in range(from_index, to_index)
        )

    def get_deposit_count(self) -> int:
        key = SchemaV1.make_deposit_data_count_lookup_key()
        try:
            raw_bytes = self.db[key]
        except KeyError:
            return 0
        return ssz.decode(raw_bytes, sedes=ssz.sedes.uint64)

    @staticmethod
    def _set_deposit_data(
        db: DatabaseAPI, index: int, deposit_data: DepositData
    ) -> None:
        db[SchemaV1.make_deposit_data_lookup_key(index)] = ssz.encode(deposit_data)

    @staticmethod
    def _set_deposit_count(db: DatabaseAPI, deposit_count: int) -> None:
        db[SchemaV1.make_deposit_data_count_lookup_key()] = ssz.encode(
            deposit_count, sedes=ssz.sedes.uint64
        )
