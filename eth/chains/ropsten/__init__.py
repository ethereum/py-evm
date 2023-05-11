from typing import Tuple, Type
from eth_typing import BlockNumber
from eth_utils import decode_hex

from .constants import (
    BERLIN_ROPSTEN_BLOCK,
    BYZANTIUM_ROPSTEN_BLOCK,
    CONSTANTINOPLE_ROPSTEN_BLOCK,
    ISTANBUL_ROPSTEN_BLOCK,
    MUIR_GLACIER_ROPSTEN_BLOCK,
    PETERSBURG_ROPSTEN_BLOCK,
    ROPSTEN_CHAIN_ID,
    SPURIOUS_DRAGON_ROPSTEN_BLOCK,
    TANGERINE_WHISTLE_ROPSTEN_BLOCK,
)
from eth import constants

from eth.abc import VirtualMachineAPI
from eth.chains.base import Chain
from eth.rlp.headers import BlockHeader
from eth.vm.forks import (
    BerlinVM,
    ByzantiumVM,
    ConstantinopleVM,
    IstanbulVM,
    MuirGlacierVM,
    PetersburgVM,
    SpuriousDragonVM,
    TangerineWhistleVM,
)


ROPSTEN_VM_CONFIGURATION = (
    # Note: Frontier and Homestead are excluded since this chain
    # starts at Tangerine Whistle.
    (TANGERINE_WHISTLE_ROPSTEN_BLOCK, TangerineWhistleVM),
    (SPURIOUS_DRAGON_ROPSTEN_BLOCK, SpuriousDragonVM),
    (BYZANTIUM_ROPSTEN_BLOCK, ByzantiumVM),
    (CONSTANTINOPLE_ROPSTEN_BLOCK, ConstantinopleVM),
    (PETERSBURG_ROPSTEN_BLOCK, PetersburgVM),
    (ISTANBUL_ROPSTEN_BLOCK, IstanbulVM),
    (MUIR_GLACIER_ROPSTEN_BLOCK, MuirGlacierVM),
    (BERLIN_ROPSTEN_BLOCK, BerlinVM),
)


class BaseRopstenChain:
    vm_configuration: Tuple[
        Tuple[BlockNumber, Type[VirtualMachineAPI]], ...
    ] = ROPSTEN_VM_CONFIGURATION
    chain_id: int = ROPSTEN_CHAIN_ID


class RopstenChain(BaseRopstenChain, Chain):
    pass


ROPSTEN_GENESIS_HEADER = BlockHeader(
    difficulty=1048576,
    extra_data=decode_hex(
        "0x3535353535353535353535353535353535353535353535353535353535353535"
    ),
    gas_limit=16777216,
    gas_used=0,
    bloom=0,
    mix_hash=constants.ZERO_HASH32,
    nonce=constants.GENESIS_NONCE,
    block_number=constants.GENESIS_BLOCK_NUMBER,
    parent_hash=constants.ZERO_HASH32,
    receipt_root=constants.BLANK_ROOT_HASH,
    uncles_hash=constants.EMPTY_UNCLE_HASH,
    state_root=decode_hex(
        "0x217b0bbcfb72e2d57e28f33cb361b9983513177755dc3f33ce3e7022ed62b77b"
    ),
    timestamp=0,
    transaction_root=constants.BLANK_ROOT_HASH,
)
