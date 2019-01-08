from .main import (  # noqa: F401
    BaseRPCModule,
    BeaconRPCModule,
    ChainReplacementEvent,
    Eth1RPCModule,
    initialize_modules,
    RPCModule,
)

from .beacon import Beacon  # noqa: F401
from .eth import Eth  # noqa: F401
from .evm import EVM  # noqa: F401
from .net import Net  # noqa: F401
from .web3 import Web3  # noqa: F401


ETH1_RPC_MODULES = (Eth, EVM, Net, Web3)
BEACON_RPC_MODULES = (Beacon,)
