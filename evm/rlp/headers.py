import time

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

from evm.utils.keccak import (
    keccak,
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
        ('block_number', big_endian_int),
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
                 block_number,
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
            parent_hash=parent_hash,
            uncles_hash=uncles_hash,
            coinbase=coinbase,
            state_root=state_root,
            transaction_root=transaction_root,
            receipts_root=receipts_root,
            bloom=bloom,
            difficulty=difficulty,
            block_number=block_number,
            gas_limit=gas_limit,
            gas_used=gas_used,
            timestamp=timestamp,
            extra_data=extra_data,
            mix_hash=mix_hash,
            nonce=nonce,
        )

    @property
    def hash(self):
        return keccak(rlp.encode(self))

    @classmethod
    def from_parent(cls, parent, coinbase, timestamp=None, nonce=None, extra_data=None):
        if timestamp is None:
            timestamp = int(time.time())

        kwargs = {
            'parent_hash': parent.hash,
            'coinbase': coinbase,
            'state_root': parent.state_root,
            'gas_limit': parent.gas_limit,  # TODO: compute gas_limit
            'difficulty': parent.difficulty,  # TODO: compute difficulty
            'block_number': parent.block_number + 1,
            'timestamp': timestamp,
        }
        if nonce is not None:
            kwargs['nonce'] = nonce
        if extra_data is not None:
            kwargs['extra_data'] = extra_data

        header = cls(**kwargs)
        return header
