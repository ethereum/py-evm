try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")

import time

from eth.constants import (
    BLANK_ROOT_HASH,
    EMPTY_UNCLE_HASH,
    GENESIS_BLOCK_NUMBER,
    GENESIS_COINBASE,
    GENESIS_DIFFICULTY,
    GENESIS_EXTRA_DATA,
    GENESIS_MIX_HASH,
    GENESIS_NONCE,
    GENESIS_PARENT_HASH,
)
from eth.rlp.headers import BlockHeader


class BlockHeaderFactory(factory.Factory):
    class Meta:
        model = BlockHeader

    parent_hash = GENESIS_PARENT_HASH
    uncles_hash = EMPTY_UNCLE_HASH
    coinbase = GENESIS_COINBASE
    state_root = BLANK_ROOT_HASH
    transaction_root = BLANK_ROOT_HASH
    receipt_root = BLANK_ROOT_HASH
    bloom = 0
    difficulty = GENESIS_DIFFICULTY
    block_number = GENESIS_BLOCK_NUMBER
    gas_limit = 0
    gas_used = 0
    timestamp = factory.LazyFunction(lambda: int(time.time()))
    extra_data = GENESIS_EXTRA_DATA
    mix_hash = GENESIS_MIX_HASH
    nonce = GENESIS_NONCE
