from typing import (
    Any,
    Iterable,
)

from eth_utils import (
    to_tuple,
)

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.chains.base import (
    BaseAsyncChain
)

from .main import (  # noqa: F401
    BaseRPCModule,
    BeaconChainRPCModule,
    ChainReplacementEvent,
    Eth1ChainRPCModule,
    ChainBasedRPCModule,
)

from .admin import Admin
from .beacon import Beacon  # noqa: F401
from .eth import Eth  # noqa: F401
from .evm import EVM  # noqa: F401
from .net import Net  # noqa: F401
from .web3 import Web3  # noqa: F401


@to_tuple
def initialize_eth1_modules(chain: BaseAsyncChain,
                            event_bus: TrinityEventBusEndpoint) -> Iterable[BaseRPCModule]:
    yield Eth(chain, event_bus)
    yield EVM(chain, event_bus)
    yield Net(event_bus)
    yield Web3()
    yield Admin(event_bus)


@to_tuple
def initialize_beacon_modules(chain: Any,
                              event_bus: TrinityEventBusEndpoint) -> Iterable[BaseRPCModule]:
    yield Beacon(chain, event_bus)
