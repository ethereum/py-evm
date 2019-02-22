from abc import (
    abstractmethod,
    ABC,
)
from typing import (
    Any,
    Generic,
    TypeVar,
    TYPE_CHECKING,
)

from lahja import (
    BaseEvent,
)

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)

if TYPE_CHECKING:
    from trinity.chains.base import BaseAsyncChain  # noqa: F401


TChain = TypeVar('TChain')


class ChainReplacementEvent(BaseEvent, Generic[TChain]):

    def __init__(self, chain: TChain):
        self.chain = chain


class BaseRPCModule(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class ChainBasedRPCModule(BaseRPCModule, Generic[TChain]):

    def __init__(self, chain: TChain, event_bus: TrinityEventBusEndpoint) -> None:
        self.chain = chain
        self.event_bus = event_bus

        self.event_bus.subscribe(
            ChainReplacementEvent,
            lambda ev: self.on_chain_replacement(ev.chain)
        )

    def on_chain_replacement(self, chain: TChain) -> None:
        self.chain = chain


Eth1ChainRPCModule = ChainBasedRPCModule['BaseAsyncChain']
BeaconChainRPCModule = ChainBasedRPCModule[Any]
