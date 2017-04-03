import rlp
from rlp.sedes import (
    big_endian_int,
    Binary,
    binary,
)

from evm.constants import (
    ZERO_HASH32,
    EMPTY_UNCLE_HASH,
    GENESIS_NONCE,
    BLANK_ROOT_HASH,
)

from .sedes import (
    address,
    hash32,
    int256,
    trie_root,
)


class BlockHeader(rlp.Serializable):
    fields = [
        ('parent_hash', hash32),
        ('uncles_hash', hash32),
        ('coinbase', address),
        ('state_root', trie_root),
        ('transaction_root', trie_root),
        ('receipts_root', trie_root),
        ('bloom', int256),
        ('difficulty', big_endian_int),
        ('number', big_endian_int),
        ('gas_limit', big_endian_int),
        ('gas_used', big_endian_int),
        ('timestamp', big_endian_int),
        ('extra_data', binary),
        ('mix_hash', binary),
        ('nonce', Binary(8, allow_empty=True))
    ]

    def __init__(self,
                 coinbase,
                 difficulty,
                 number,
                 gas_limit,
                 timestamp,
                 parent_hash=ZERO_HASH32,
                 uncles_hash=EMPTY_UNCLE_HASH,
                 state_root=BLANK_ROOT_HASH,
                 transaction_root=BLANK_ROOT_HASH,
                 receipts_root=BLANK_ROOT_HASH,
                 bloom=0,
                 gas_used=0,
                 extra_data=b'',
                 mix_hash=ZERO_HASH32,
                 nonce=GENESIS_NONCE):
        super(BlockHeader, self).__init__(
            parten_hash=parent_hash,
            uncles_hash=uncles_hash,
            coinbase=coinbase,
            state_root=state_root,
            transaction_root=transaction_root,
            receipts_root=receipts_root,
            bloom=bloom,
            difficulty=difficulty,
            number=number,
            gas_limit=gas_limit,
            gas_used=gas_used,
            timestamp=timestamp,
            extra_data=extra_data,
            mix_hash=mix_hash,
            nonce=nonce,
        )

#
#        coinbase=fixture['env']['currentCoinbase'],
#        difficulty=fixture['env']['currentDifficulty'],
#        block_number=fixture['env']['currentNumber'],
#        gas_limit=fixture['env']['currentGasLimit'],
#        timestamp=fixture['env']['currentTimestamp'],
#        previous_hash=fixture['env']['previousHash'],
