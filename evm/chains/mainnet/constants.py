ZERO_HASH32 = 32 * b'\x00'


#
# ByzantiumVM
#
BYZANTIUM_MAINNET_BLOCK = 4370000


#
# DAO Block Number
#
DAO_FORK_BLOCK_NUMBER = 1920000


#
# Tangerine Whistle Mainnet Block
#
TANGERINE_WHISTLE_MAINNET_BLOCK = 2463000


#
# Homestead Mainnet Block
#
HOMESTEAD_MAINNET_BLOCK = 1150000


#
# Spurious Dragon Mainnet Block
#
SPURIOUS_DRAGON_MAINNET_BLOCK = 2675000


#
# Genesis Data
#
GENESIS_NONCE = b'\x00\x00\x00\x00\x00\x00\x00B'  # 0x42 encoded as big-endian-integer


#
# Sha3 Keccak
#
BLANK_ROOT_HASH = b'V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n\x5bH\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!'  # noqa: E501


#
# Block and Header
#
# keccak(rlp.encode([]))
EMPTY_UNCLE_HASH = b'\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G'  # noqa: E501
