import rlp

from .db import (
    make_block_number_to_hash_lookup_key,
    make_block_hash_to_number_lookup_key,
)


def persist_block_to_db(db, block):
    # Keep a mapping from block hash to number
    block_hash_to_number_key = make_block_hash_to_number_lookup_key(block.hash)
    db.set(
        block_hash_to_number_key,
        rlp.encode(block.header.block_number, sedes=rlp.sedes.big_endian_int),
    )

    # Keep a mapping from block number to block hash.
    block_number_to_hash_key = make_block_number_to_hash_lookup_key(
        block.header.block_number
    )
    db.set(
        block_number_to_hash_key,
        rlp.encode(block.hash, sedes=rlp.sedes.binary),
    )

    # Persist the block header
    db.set(
        block.header.hash,
        rlp.encode(block.header),
    )

    # Persist the transactions
    for transaction in block.transactions:
        db.set(
            transaction.hash,
            rlp.encode(transaction),
        )

    # Persist the uncles list
    db.set(
        block.header.uncles_hash,
        rlp.encode(block.uncles, sedes=rlp.sedes.CountableList(type(block.header))),
    )

    # Persist each individual uncle
    # TODO: is this necessary?
    for uncle in block.uncles:
        db.set(
            uncle.hash,
            rlp.encode(uncle),
        )
