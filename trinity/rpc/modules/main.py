from abc import (
    abstractmethod,
    ABC,
)
from typing import (
    Any,
    Generic,
    Iterable,
    Type,
    TypeVar,
    TYPE_CHECKING,
)

from eth_utils import (
    to_tuple,
)
from lahja import (
    BaseEvent,
    Endpoint
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


class RPCModule(BaseRPCModule, Generic[TChain]):

    def __init__(self, chain: TChain, event_bus: Endpoint) -> None:
        self.chain = chain
        self.event_bus = event_bus

        self.event_bus.subscribe(
            ChainReplacementEvent,
            lambda ev: self.set_chain(ev.chain)
        )

    def set_chain(self, chain: TChain) -> None:
        self.chain = chain


Eth1RPCModule = RPCModule['BaseAsyncChain']
BeaconRPCModule = RPCModule[Any]


@to_tuple
def initialize_modules(modules: Iterable[Type[RPCModule[TChain]]],
                       chain: TChain,
                       event_bus: Endpoint) -> Iterable[RPCModule[TChain]]:

    for module in modules:
        yield module(chain, event_bus)
