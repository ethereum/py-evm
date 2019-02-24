from typing import (
    Dict,
    NamedTuple,
    Set,
)

from eth2.beacon.typing import (
    Gwei,
    ValidatorIndex,
)


class RewardsSettlementContext(NamedTuple):
    rewards_received: Dict[ValidatorIndex, Gwei]
    penalties_received: Dict[ValidatorIndex, Gwei]
    rewards: Dict[ValidatorIndex, Gwei] = dict()
    indices_to_reward: Set[ValidatorIndex] = set()
    penalties: Dict[ValidatorIndex, Gwei] = dict()
    indices_to_penalize: Set[ValidatorIndex] = set()
