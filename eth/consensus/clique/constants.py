from eth_utils import (
    decode_hex,
)

ALLOWED_CLIQUE_DIFFICULTIES = {1, 2}

COMMON_ADDRESS_LENGTH = 20

EPOCH_LENGTH = 30000

IN_MEMORY_SNAPSHOTS = 128

NONCE_AUTH = decode_hex("0xffffffffffffffff")
NONCE_DROP = decode_hex("0x0000000000000000")

# Indicate the byte length required to carry a signature with recovery id.
# 64 bytes ECDSA signature + 1 byte recovery id
SIGNATURE_LENGTH = 64 + 1

# Indicate the byte length reserved as vanity space in extra_data
VANITY_LENGTH = 32
