from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.typing import (
    BLSSignature,
    Epoch
)


EMPTY_SIGNATURE = BLSSignature(b'\x00' * 96)
GWEI_PER_ETH = 10**9
FAR_FUTURE_EPOCH = Epoch(2**64 - 1)

GENESIS_PARENT_ROOT = ZERO_HASH32

#
# shuffle function
#

POWER_OF_TWO_NUMBERS = [1, 2, 4, 8, 16, 32, 64, 128]
MAX_LIST_SIZE = 2**40
