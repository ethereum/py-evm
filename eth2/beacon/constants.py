from eth.constants import (
    ZERO_HASH32,
)
from eth_typing import (
    BLSSignature,
)
from eth2.beacon.typing import (
    Epoch,
    Timestamp,
)


EMPTY_SIGNATURE = BLSSignature(b'\x00' * 96)
GWEI_PER_ETH = 10**9
FAR_FUTURE_EPOCH = Epoch(2**64 - 1)

GENESIS_PARENT_ROOT = ZERO_HASH32

ZERO_TIMESTAMP = Timestamp(0)

#
# shuffle function
#

POWER_OF_TWO_NUMBERS = [1, 2, 4, 8, 16, 32, 64, 128]
MAX_LIST_SIZE = 2**40
