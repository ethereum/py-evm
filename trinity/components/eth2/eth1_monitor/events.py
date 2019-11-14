from dataclasses import dataclass
from typing import Generic, TypeVar, Type
import ssz

from lahja import BaseEvent, BaseRequestResponseEvent

from eth_typing import BlockNumber

from eth2.beacon.typing import Timestamp
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.eth1_data import Eth1Data


TData = TypeVar("TData", Deposit, Eth1Data)


@dataclass
class SSZSerializableEvent(BaseEvent, Generic[TData]):
    TSSZEvent = TypeVar("TSSZEvent", bound="SSZSerializableEvent[TData]")

    sedes: Type[TData]
    data_bytes: bytes
    error: Exception = None

    @classmethod
    def from_data(cls: Type[TSSZEvent], data: TData) -> TSSZEvent:
        return cls(sedes=cls.sedes, data_bytes=ssz.encode(data))

    def to_data(self) -> TData:
        if self.error is not None:
            raise self.error
        return ssz.decode(self.data_bytes, self.sedes)


class GetDepositResponse(SSZSerializableEvent[Deposit]):
    sedes = Deposit


@dataclass
class GetDepositRequest(BaseRequestResponseEvent[GetDepositResponse]):
    deposit_count: int
    deposit_index: int

    @staticmethod
    def expected_response_type() -> Type[GetDepositResponse]:
        return GetDepositResponse


class GetEth1DataResponse(SSZSerializableEvent[Eth1Data]):
    sedes = Eth1Data


@dataclass
class GetEth1DataRequest(BaseRequestResponseEvent[GetEth1DataResponse]):
    distance: BlockNumber
    eth1_voting_period_start_timestamp: Timestamp

    @staticmethod
    def expected_response_type() -> Type[GetEth1DataResponse]:
        return GetEth1DataResponse
