from abc import ABC, abstractmethod

from typing import List, Optional, Sequence, Tuple

import ssz

from eth_typing import BlockNumber

from eth.abc import AtomicDatabaseAPI, DatabaseAPI

from eth2.beacon.types.deposit_data import DepositData

from .exceptions import DepositDataDBValidationError


class BaseSchema(ABC):
    @staticmethod
    @abstractmethod
    def make_deposit_data_lookup_key(index: int) -> bytes:
        ...

    @staticmethod
    @abstractmethod
    def make_deposit_count_lookup_key() -> bytes:
        ...

    @staticmethod
    @abstractmethod
    def make_highest_processed_block_number_lookup_key() -> bytes:
        ...


class SchemaV1(BaseSchema):
    @staticmethod
    def make_deposit_data_lookup_key(index: int) -> bytes:
        return b"v1:deposit_data:" + index.to_bytes(8, "big")

    @staticmethod
    def make_deposit_count_lookup_key() -> bytes:
        return b"v1:deposit_data:count"

    @staticmethod
    def make_highest_processed_block_number_lookup_key() -> bytes:
        return b"v1:deposit_data:highest_processed_block_number"


class BaseDepositDataDB(ABC):
    @property
    @abstractmethod
    def deposit_count(self) -> int:
        ...

    @property
    @abstractmethod
    def highest_processed_block_number(self) -> BlockNumber:
        ...

    @abstractmethod
    def add_deposit_data_batch(
        self, seq_deposit_data: Sequence[DepositData], block_number: BlockNumber
    ) -> None:
        ...

    @abstractmethod
    def get_deposit_data(self, index: int) -> DepositData:
        ...

    @abstractmethod
    def get_deposit_data_range(
        self, from_index: int, to_index: int
    ) -> Tuple[DepositData, ...]:
        ...


def _validate_deposit_data_index(index: int, deposit_count: int) -> None:
    if index >= deposit_count:
        raise DepositDataDBValidationError(
            "`index` should be smaller than `self.deposit_count`: "
            f"index={index}, self.deposit_count={deposit_count}"
        )


def _validate_deposit_data_range_indices(
    from_index: int, to_index: int, deposit_count: int
) -> None:
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
    if (from_index >= deposit_count) or (to_index > deposit_count):
        raise DepositDataDBValidationError(
            "either `from_index` or `to_index` is larger or equaled to `self.deposit_count`: "
            f"from_index={from_index}, to_index={to_index}, "
            f"self.deposit_count={deposit_count}"
        )


class DepositDataDB(BaseDepositDataDB):
    db: AtomicDatabaseAPI

    _deposit_count: int
    _highest_processed_block_number: BlockNumber

    def __init__(
        self,
        db: AtomicDatabaseAPI,
        highest_processed_block_number: Optional[BlockNumber] = None,
    ) -> None:
        self.db = db
        self._deposit_count = self._get_deposit_count()
        # If the parameter `highest_processed_block_number` is given, set it in the database.
        if highest_processed_block_number is not None:
            if highest_processed_block_number < 0:
                raise DepositDataDBValidationError(
                    "`highest_processed_block_number` should be non-negative: "
                    f"highest_processed_block_number={highest_processed_block_number}"
                )
            self._set_highest_processed_block_number(
                self.db, highest_processed_block_number
            )
        self._highest_processed_block_number = (
            self._get_highest_processed_block_number()
        )

    @property
    def deposit_count(self) -> int:
        return self._deposit_count

    @property
    def highest_processed_block_number(self) -> BlockNumber:
        return self._highest_processed_block_number

    def add_deposit_data_batch(
        self, seq_deposit_data: Sequence[DepositData], block_number: BlockNumber
    ) -> None:
        if block_number <= self.highest_processed_block_number:
            raise DepositDataDBValidationError(
                "`block_number` should be larger than `self.highest_processed_block_number`: "
                f"`block_number`={block_number}, "
                f"`self.highest_processed_block_number`={self.highest_processed_block_number}"
            )
        count = self.deposit_count
        new_count = count + len(seq_deposit_data)
        with self.db.atomic_batch() as db:
            for index, data in enumerate(seq_deposit_data):
                self._set_deposit_data(db, count + index, data)
            self._set_deposit_count(db, new_count)
            self._set_highest_processed_block_number(db, block_number)
        self._deposit_count = new_count
        self._highest_processed_block_number = block_number

    def get_deposit_data(self, index: int) -> DepositData:
        _validate_deposit_data_index(index, self.deposit_count)
        key = SchemaV1.make_deposit_data_lookup_key(index)
        try:
            raw_bytes = self.db[key]
        except KeyError as error:
            # Should never enter here. Something strange must have happened.
            raise Exception(
                f"`index < self.deposit_count` but failed to find `DepositData` at key {key!r}: "
                f"index={index}, self.deposit_count={self.deposit_count}"
            ) from error
        return ssz.decode(raw_bytes, DepositData)

    def get_deposit_data_range(
        self, from_index: int, to_index: int
    ) -> Tuple[DepositData, ...]:
        _validate_deposit_data_range_indices(from_index, to_index, self.deposit_count)
        return tuple(
            self.get_deposit_data(index) for index in range(from_index, to_index)
        )

    def _get_deposit_count(self) -> int:
        key = SchemaV1.make_deposit_count_lookup_key()
        try:
            raw_bytes = self.db[key]
        except KeyError:
            return 0
        return self._deserialize_uint(raw_bytes)

    def _get_highest_processed_block_number(self) -> BlockNumber:
        key = SchemaV1.make_highest_processed_block_number_lookup_key()
        try:
            raw_bytes = self.db[key]
        except KeyError:
            return BlockNumber(0)
        return BlockNumber(self._deserialize_uint(raw_bytes))

    @staticmethod
    def _set_deposit_data(
        db: DatabaseAPI, index: int, deposit_data: DepositData
    ) -> None:
        db[SchemaV1.make_deposit_data_lookup_key(index)] = ssz.encode(deposit_data)

    @classmethod
    def _set_deposit_count(cls, db: DatabaseAPI, deposit_count: int) -> None:
        db[SchemaV1.make_deposit_count_lookup_key()] = cls._serialize_uint(
            deposit_count
        )

    @classmethod
    def _set_highest_processed_block_number(
        cls, db: DatabaseAPI, block_number: BlockNumber
    ) -> None:
        key = SchemaV1.make_highest_processed_block_number_lookup_key()
        db[key] = cls._serialize_uint(block_number)

    @staticmethod
    def _serialize_uint(item: int) -> bytes:
        return ssz.encode(item, sedes=ssz.sedes.uint64)

    @staticmethod
    def _deserialize_uint(item_bytes: bytes) -> int:
        return ssz.decode(item_bytes, sedes=ssz.sedes.uint64)


class ListCachedDepositDataDB(BaseDepositDataDB):
    _cache_deposit_data: List[DepositData]
    _db: BaseDepositDataDB

    def __init__(
        self,
        db: AtomicDatabaseAPI,
        highest_processed_block_number: Optional[BlockNumber] = None,
    ) -> None:
        self._db: BaseDepositDataDB = DepositDataDB(db, highest_processed_block_number)
        self._cache_deposit_data = []
        self._update_cache()

    @property
    def deposit_count(self) -> int:
        return self._db.deposit_count

    @property
    def highest_processed_block_number(self) -> BlockNumber:
        return self._db.highest_processed_block_number

    def add_deposit_data_batch(
        self, seq_deposit_data: Sequence[DepositData], block_number: BlockNumber
    ) -> None:
        self._db.add_deposit_data_batch(seq_deposit_data, block_number)
        self._cache_deposit_data.extend(seq_deposit_data)

    def get_deposit_data(self, index: int) -> DepositData:
        _validate_deposit_data_index(index, self.deposit_count)
        return self._cache_deposit_data[index]

    def get_deposit_data_range(
        self, from_index: int, to_index: int
    ) -> Tuple[DepositData, ...]:
        _validate_deposit_data_range_indices(from_index, to_index, self.deposit_count)
        # Use `tuple(range())` instead of slice operator to ensure it is the similar behavior
        #   as `range`.
        return tuple(
            self.get_deposit_data(index) for index in range(from_index, to_index)
        )

    def _update_cache(self) -> None:
        if self.deposit_count != 0:
            self._cache_deposit_data = list(
                self._db.get_deposit_data_range(0, self.deposit_count)
            )
        else:
            self._cache_deposit_data = []
