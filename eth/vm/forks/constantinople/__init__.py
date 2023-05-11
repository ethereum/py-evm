from typing import (
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth.vm.forks.byzantium import (
    ByzantiumVM,
    get_uncle_reward,
)
from eth.vm.state import BaseState

from .blocks import ConstantinopleBlock
from .constants import EIP1234_BLOCK_REWARD
from .headers import (
    compute_constantinople_difficulty,
    configure_constantinople_header,
    create_constantinople_header_from_parent,
)
from .state import ConstantinopleState


class ConstantinopleVM(ByzantiumVM):
    # fork name
    fork = "constantinople"

    # classes
    block_class: Type[BaseBlock] = ConstantinopleBlock
    _state_class: Type[BaseState] = ConstantinopleState

    # Methods
    create_header_from_parent = staticmethod(create_constantinople_header_from_parent)  # type: ignore  # noqa: E501
    compute_difficulty = staticmethod(compute_constantinople_difficulty)  # type: ignore
    configure_header = configure_constantinople_header
    get_uncle_reward = staticmethod(get_uncle_reward(EIP1234_BLOCK_REWARD))

    @staticmethod
    def get_block_reward() -> int:
        return EIP1234_BLOCK_REWARD
