from abc import (
    ABC,
)
from typing import (
    Any,
    Generic,
    TypeVar,
)

from lahja import (
    BaseEvent,
    EndpointAPI
)

from trinity.chains.base import AsyncChainAPI


TChain = TypeVar('TChain')


class ChainReplacementEvent(BaseEvent, Generic[TChain]):

    def __init__(self, chain: TChain):
        self.chain = chain


class BaseRPCModule(ABC):

    @property
    def name(self) -> str:
        # By default the name is the lower-case class name.
        # This encourages a standard name of the module, but can
        # be overridden if necessary.
        return self.__class__.__name__.lower()


class ChainBasedRPCModule(BaseRPCModule, Generic[TChain]):

    def __init__(self, chain: TChain, event_bus: EndpointAPI) -> None:
        self.chain = chain
        self.event_bus = event_bus

        self.event_bus.subscribe(
            ChainReplacementEvent,
            lambda ev: self.on_chain_replacement(ev.chain)
        )

    def on_chain_replacement(self, chain: TChain) -> None:
        self.chain = chain


Eth1ChainRPCModule = ChainBasedRPCModule[AsyncChainAPI]
BeaconChainRPCModule = ChainBasedRPCModule[Any]
