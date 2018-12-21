from abc import (
    abstractmethod,
    ABC,
)
from typing import (
    Iterable,
    Type,
)

from eth_utils import (
    to_tuple,
)
from lahja import (
    Endpoint
)

from trinity.chains.base import BaseAsyncChain


class RPCModule(ABC):
    _chain = None

    def __init__(self, chain: BaseAsyncChain, event_bus: Endpoint) -> None:
        self._chain = chain
        self._event_bus = event_bus

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def set_chain(self, chain: BaseAsyncChain) -> None:
        self._chain = chain


@to_tuple
def initialize_modules(modules: Iterable[Type[RPCModule]],
                       chain: BaseAsyncChain,
                       event_bus: Endpoint) -> Iterable[RPCModule]:

    for module in modules:
        yield module(chain, event_bus)
