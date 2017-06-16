import rlp

from .db import (
    make_block_number_to_hash_lookup_key,
    make_block_hash_to_number_lookup_key,
)


def persist_block_to_db(db, block):
    # Store mapping from block hash to number
    block_hash_to_number_key = make_block_hash_to_number_lookup_key(block.hash)
    db.set(
        block_hash_to_number_key,
        rlp.encode(block.header.block_number, sedes=rlp.sedes.big_endian_int),
    )

    # Store mapping from block number to block hash.
    block_number_to_hash_key = make_block_number_to_hash_lookup_key(
        block.header.block_number
    )
    db.set(
        block_number_to_hash_key,
        rlp.encode(block.hash, sedes=rlp.sedes.binary),
    )

    # Store the block itself.
    db.set(
        block.hash,
        rlp.encode(block),
    )
