from eth_utils import decode_hex

from evm import constants
from evm.chains.chain import Chain

from evm.rlp.headers import BlockHeader
from evm.vm.forks import (
    EIP150VM,
    FrontierVM,
    HomesteadVM,
    SpuriousDragonVM,
    ByzantiumVM,
)


MAINNET_VM_CONFIGURATION = (
    (0, FrontierVM),
    (constants.HOMESTEAD_MAINNET_BLOCK, HomesteadVM),
    (constants.EIP150_MAINNET_BLOCK, EIP150VM),
    (constants.SPURIOUS_DRAGON_MAINNET_BLOCK, SpuriousDragonVM),
    (constants.BYZANTIUM_MAINNET_BLOCK, ByzantiumVM),
)


MAINNET_NETWORK_ID = 1


MainnetChain = Chain.configure(
    'MainnetChain',
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=MAINNET_NETWORK_ID,
)


MAINNET_GENESIS_HEADER = BlockHeader(
    difficulty=17179869184,
    extra_data=decode_hex("0x11bbe8db4e347b4e8c937c1c8370e4b5ed33adb3db69cbdb7a38e1e50b1b82fa"),
    gas_limit=5000,
    gas_used=0,
    bloom=0,
    mix_hash=constants.ZERO_HASH32,
    nonce=constants.GENESIS_NONCE,
    block_number=0,
    parent_hash=constants.ZERO_HASH32,
    receipt_root=constants.BLANK_ROOT_HASH,
    uncles_hash=constants.EMPTY_UNCLE_HASH,
    state_root=decode_hex("0xd7f8974fb5ac78d9ac099b9ad5018bedc2ce0a72dad1827a1709da30580f0544"),
    timestamp=0,
    transaction_root=constants.BLANK_ROOT_HASH,
)
