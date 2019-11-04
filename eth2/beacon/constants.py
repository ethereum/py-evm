from eth.constants import ZERO_HASH32
from eth_typing import BLSPubkey, BLSSignature

from eth2.beacon.typing import Epoch, HashTreeRoot, SigningRoot, Timestamp

EMPTY_SIGNATURE = BLSSignature(b"\x00" * 96)
EMPTY_PUBKEY = BLSPubkey(b"\x00" * 48)
GWEI_PER_ETH = 10 ** 9
FAR_FUTURE_EPOCH = Epoch(2 ** 64 - 1)

ZERO_SIGNING_ROOT = SigningRoot(ZERO_HASH32)
ZERO_HASH_TREE_ROOT = HashTreeRoot(ZERO_HASH32)
GENESIS_PARENT_ROOT = ZERO_SIGNING_ROOT

ZERO_TIMESTAMP = Timestamp(0)

MAX_INDEX_COUNT = 2 ** 40

MAX_RANDOM_BYTE = 2 ** 8 - 1

BASE_REWARDS_PER_EPOCH = 4

DEPOSIT_CONTRACT_TREE_DEPTH = 2 ** 5

SECONDS_PER_DAY = 86400

JUSTIFICATION_BITS_LENGTH = 4
