from eth_typing import (
    BlockNumber,
)

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

DAO_FORK_MAINNET_EXTRA_DATA = b"dao-hard-fork"


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

#
# Istanbul Block
#
ISTANBUL_MAINNET_BLOCK = BlockNumber(9069000)

#
# Muir Glacier Block
#
MUIR_GLACIER_MAINNET_BLOCK = BlockNumber(9200000)

#
# Berlin Block
#
BERLIN_MAINNET_BLOCK = BlockNumber(12244000)

#
# London Block
#
LONDON_MAINNET_BLOCK = BlockNumber(12965000)

#
# Arrow Glacier Block
#
ARROW_GLACIER_MAINNET_BLOCK = BlockNumber(13773000)

#
# Gray Glacier Block
#
GRAY_GLACIER_MAINNET_BLOCK = BlockNumber(15050000)

#
# Paris Block (block height at which TTD was reached)
#
PARIS_MAINNET_BLOCK = BlockNumber(15537394)
