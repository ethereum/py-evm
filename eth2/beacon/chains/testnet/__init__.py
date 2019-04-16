from typing import (
    TYPE_CHECKING,
)
from eth2.beacon.chains.base import (
    BeaconChain,
)
from eth2.beacon.state_machines.forks.xiao_long_bao import (
    XiaoLongBaoStateMachine,
)
from .constants import GENESIS_SLOT, TESTNET_CHAIN_ID

if TYPE_CHECKING:
    from eth2.beacon.typing import (  # noqa: F401
        Slot,
    )
    from eth2.beacon.state_machines.base import (  # noqa: F401
        BaseBeaconStateMachine,
    )
    from typing import (  # noqa: F401
        Tuple,
        Type,
    )


TESTNET_SM_CONFIGURATION = (
    (GENESIS_SLOT, XiaoLongBaoStateMachine),
)  # type: Tuple[Tuple[Slot, Type[BaseBeaconStateMachine]], ...]


class BaseTestnetChain:
    sm_configuration = TESTNET_SM_CONFIGURATION
    chain_id = TESTNET_CHAIN_ID


class TestnetChain(BaseTestnetChain, BeaconChain):
    pass
