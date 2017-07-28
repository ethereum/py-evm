import rlp

from evm.constants import (
    GENESIS_DIFFICULTY,
    GENESIS_PARENT_HASH,
)
from evm.exceptions import (
    BlockNotFound,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.utils.hexidecimal import (
    encode_hex,
)
from evm.validation import (
    validate_uint256,
    validate_word,
)
from .db import (
    make_block_hash_to_score_lookup_key,
    make_block_number_to_hash_lookup_key,
)


def add_block_number_to_hash_lookup(db, block):
    block_number_to_hash_key = make_block_number_to_hash_lookup_key(
        block.header.block_number
    )
    db.set(
        block_number_to_hash_key,
        rlp.encode(block.hash, sedes=rlp.sedes.binary),
    )


def get_score(db, block_hash):
    # TODO: This may be a problem as not all chains will start with the same
    # genesis difficulty. Maybe make it Chain aware so that it can pull the
    # genesis block and pull the genesis difficulty from there.
    if block_hash == GENESIS_PARENT_HASH:
        return GENESIS_DIFFICULTY
    return rlp.decode(
        db.get(make_block_hash_to_score_lookup_key(block_hash)),
        sedes=rlp.sedes.big_endian_int)


def persist_block_to_db(db, block):
    # Persist the block header
    db.set(
        block.header.hash,
        rlp.encode(block.header),
    )

    score = get_score(db, block.header.parent_hash) + block.header.difficulty
    db.set(
        make_block_hash_to_score_lookup_key(block.hash),
        rlp.encode(score, sedes=rlp.sedes.big_endian_int))

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


def get_block_header_by_hash(db, block_hash):
    """
    Returns the requested block header as specified by block hash.

    Raises BlockNotFound if it is not present in the db.
    """
    validate_word(block_hash)
    try:
        block = db.get(block_hash)
    except KeyError:
        raise BlockNotFound("No block with hash {0} found".format(
            encode_hex(block_hash)))
    return rlp.decode(block, sedes=BlockHeader)


def lookup_block_hash(db, block_number):
    """
    Return the block hash for the given block number.
    """
    validate_uint256(block_number)
    number_to_hash_key = make_block_number_to_hash_lookup_key(block_number)
    # TODO: can raise KeyError
    block_hash = rlp.decode(
        db.get(number_to_hash_key),
        sedes=rlp.sedes.binary,
    )
    return block_hash
