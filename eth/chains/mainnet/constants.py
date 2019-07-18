from eth_typing import BlockNumber


# https://github.com/ethereum/EIPs/blob/master/EIPS/eip-155.md
MAINNET_CHAIN_ID = 1

# Fork Blocks listed in ascending order


#
# Homestead Block
#
HOMESTEAD_MAINNET_BLOCK = BlockNumber(1150000)


#
# DAO Block
#
DAO_FORK_MAINNET_BLOCK = BlockNumber(1920000)

DAO_FORK_MAINNET_EXTRA_DATA = b'dao-hard-fork'


#
# Tangerine Whistle Block
#
TANGERINE_WHISTLE_MAINNET_BLOCK = BlockNumber(2463000)


#
# Spurious Dragon Block
#
SPURIOUS_DRAGON_MAINNET_BLOCK = BlockNumber(2675000)


#
# Byzantium Block
#
BYZANTIUM_MAINNET_BLOCK = BlockNumber(4370000)

#
# Petersburg Block
#
PETERSBURG_MAINNET_BLOCK = BlockNumber(7280000)
