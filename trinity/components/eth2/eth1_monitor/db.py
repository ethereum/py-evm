from abc import ABC, abstractmethod

from typing import Optional, Sequence, Tuple

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


class SchemaV1(BaseSchema):
    @staticmethod
    def make_deposit_data_lookup_key(index: int) -> bytes:
        index_in_str = str(index)
        return b"v1:deposit_data:" + index_in_str.encode()

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

    @abstractmethod
    def get_deposit_count(self) -> int:
        ...


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
        self._deposit_count = self.get_deposit_count()
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
        self._highest_processed_block_number = self.get_highest_processed_block_number()

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
        if index >= self.deposit_count:
            raise DepositDataDBValidationError(
                "`index` should be smaller than `self.deposit_count`: "
                f"index={index}, self.deposit_count={self.deposit_count}"
            )
        key = SchemaV1.make_deposit_data_lookup_key(index)
        try:
            raw_bytes = self.db[key]
        except KeyError:
            # Should never enter here. Something strange must have happened.
            raise Exception(
                f"`index < self.deposit_count` but failed to find `DepositData` at key {key}: "
                f"index={index}, self.deposit_count={self.deposit_count}"
            )
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
        key = SchemaV1.make_deposit_count_lookup_key()
        try:
            raw_bytes = self.db[key]
        except KeyError:
            return 0
        return self._deserialize_uint(raw_bytes)

    def get_highest_processed_block_number(self) -> BlockNumber:
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
        db[
            SchemaV1.make_highest_processed_block_number_lookup_key()
        ] = cls._serialize_uint(block_number)

    @staticmethod
    def _serialize_uint(item: int) -> bytes:
        return ssz.encode(item, sedes=ssz.sedes.uint64)

    @staticmethod
    def _deserialize_uint(item_bytes: bytes) -> int:
        return ssz.decode(item_bytes, sedes=ssz.sedes.uint64)
