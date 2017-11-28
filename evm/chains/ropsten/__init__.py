from eth_utils import decode_hex

from evm import constants
from evm.chains.chain import Chain
from evm.chains.mainnet import MAINNET_VM_CONFIGURATION
from evm.rlp.headers import BlockHeader


ROPSTEN_NETWORK_ID = 3


RopstenChain = Chain.configure(
    'RopstenChain',
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=ROPSTEN_NETWORK_ID,
)


ROPSTEN_GENESIS_HEADER = BlockHeader(
    difficulty=1048576,
    extra_data=decode_hex("0x3535353535353535353535353535353535353535353535353535353535353535"),
    gas_limit=16777216,
    gas_used=0,
    bloom=0,
    mix_hash=constants.ZERO_HASH32,
    nonce=constants.GENESIS_NONCE,
    block_number=0,
    parent_hash=constants.ZERO_HASH32,
    receipt_root=constants.BLANK_ROOT_HASH,
    uncles_hash=constants.EMPTY_UNCLE_HASH,
    state_root=decode_hex("0x217b0bbcfb72e2d57e28f33cb361b9983513177755dc3f33ce3e7022ed62b77b"),
    timestamp=0,
    transaction_root=constants.BLANK_ROOT_HASH,
)
