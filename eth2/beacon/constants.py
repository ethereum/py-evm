from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.typing import (
    BLSSignature,
    SlotNumber,
)


#
# shuffle function
#

# The size of 3 bytes in integer
# sample_range = 2 ** (3 * 8) = 2 ** 24 = 16777216
# sample_range = 16777216

# Entropy is consumed from the seed in 3-byte (24 bit) chunks.
RAND_BYTES = 3
# The highest possible result of the RNG.
RAND_MAX = 2 ** (RAND_BYTES * 8) - 1

EMPTY_SIGNATURE = BLSSignature(b'\x00' * 96)
GWEI_PER_ETH = 10**9
FAR_FUTURE_SLOT = SlotNumber(2**64 - 1)

GENESIS_PARENT_ROOT = ZERO_HASH32
