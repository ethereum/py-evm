from eth.constants import (
    ZERO_HASH32,
)
from eth_typing import (
    BLSSignature,
    BLSPubkey,
)
from eth2.beacon.typing import (
    Epoch,
    Timestamp,
)


EMPTY_SIGNATURE = BLSSignature(b'\x00' * 96)
EMPTY_PUBKEY = BLSPubkey(b'\x00' * 48)
GWEI_PER_ETH = 10**9
FAR_FUTURE_EPOCH = Epoch(2**64 - 1)

GENESIS_PARENT_ROOT = ZERO_HASH32

ZERO_TIMESTAMP = Timestamp(0)

MAX_INDEX_COUNT = 2**40

MAX_RANDOM_BYTE = 2**8 - 1

BASE_REWARDS_PER_EPOCH = 5

DEPOSIT_CONTRACT_TREE_DEPTH = 2**5
