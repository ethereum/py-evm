from cytoolz import (
    merge,
)

from evm import constants
from evm import precompiles
from evm.utils.address import (
    force_bytes_to_address,
)
from evm.validation import (
    validate_lte,
)

from ..frontier import FRONTIER_PRECOMPILES
from ..spurious_dragon import SpuriousDragonVM

from .headers import (
    create_byzantium_header_from_parent,
    configure_byzantium_header,
)
from .opcodes import BYZANTIUM_OPCODES
from .blocks import ByzantiumBlock


BYZANTIUM_PRECOMPILES = merge(
    FRONTIER_PRECOMPILES,
    {
        force_bytes_to_address(b'\x05'): precompiles.modexp,
        force_bytes_to_address(b'\x06'): precompiles.ecadd,
        force_bytes_to_address(b'\x07'): precompiles.ecmul,
        force_bytes_to_address(b'\x08'): precompiles.ecpairing,
    },
)


def _byzantium_get_block_reward(block_number):
    return constants.EIP649_BLOCK_REWARD


def _byzantium_get_uncle_reward(block_number, uncle):
    validate_lte(uncle.block_number, constants.MAX_UNCLE_DEPTH)
    block_number_delta = block_number - uncle.block_number
    return (8 - block_number_delta) * constants.EIP649_BLOCK_REWARD // 8


ByzantiumVM = SpuriousDragonVM.configure(
    name='ByzantiumVM',
    # precompiles
    _precompiles=BYZANTIUM_PRECOMPILES,
    # opcodes
    opcodes=BYZANTIUM_OPCODES,
    # RLP
    _block_class=ByzantiumBlock,
    # Methods
    create_header_from_parent=staticmethod(create_byzantium_header_from_parent),
    configure_header=configure_byzantium_header,
    get_block_reward=staticmethod(_byzantium_get_block_reward),
    get_uncle_reward=staticmethod(_byzantium_get_uncle_reward),
)
