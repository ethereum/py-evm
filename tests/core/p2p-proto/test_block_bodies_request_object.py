import os
import random
import time

import pytest

import rlp

from eth_hash.auto import keccak

from eth_utils import (
    to_tuple,
    big_endian_to_int,
    ValidationError,
)

from eth.db.trie import make_trie_root_and_nodes
from eth.rlp.headers import BlockHeader
from eth.rlp.transactions import BaseTransactionFields

from trinity.rlp.block_body import BlockBody
from trinity.protocol.eth.validators import GetBlockBodiesValidator


def mk_uncle(block_number):
    return BlockHeader(
        state_root=os.urandom(32),
        difficulty=1000000,
        block_number=block_number,
        gas_limit=3141592,
        timestamp=int(time.time()),
    )


def mk_transaction():
    return BaseTransactionFields(
        nonce=0,
        gas=21000,
        gas_price=1,
        to=os.urandom(20),
        value=random.randint(0, 100),
        data=b'',
        v=27,
        r=big_endian_to_int(os.urandom(32)),
        s=big_endian_to_int(os.urandom(32)),
    )


def mk_header_and_body(block_number, num_transactions, num_uncles):
    transactions = tuple(mk_transaction() for _ in range(num_transactions))
    uncles = tuple(mk_uncle(block_number - 1) for _ in range(num_uncles))

    transaction_root, trie_data = make_trie_root_and_nodes(transactions)
    uncles_hash = keccak(rlp.encode(uncles))

    body = BlockBody(transactions=transactions, uncles=uncles)

    header = BlockHeader(
        difficulty=1000000,
        block_number=block_number,
        gas_limit=3141592,
        timestamp=int(time.time()),
        transaction_root=transaction_root,
        uncles_hash=uncles_hash,
    )

    return header, body, transaction_root, trie_data, uncles_hash


@to_tuple
def mk_headers(*counts):
    for idx, (num_transactions, num_uncles) in enumerate(counts, 1):
        yield mk_header_and_body(idx, num_transactions, num_uncles)


def test_block_bodies_request_empty_response_is_valid():
    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, _, _, _, _ = zip(*headers_bundle)
    validator = GetBlockBodiesValidator(headers)
    validator.validate_result(tuple())


def test_block_bodies_request_valid_with_full_response():
    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, bodies, transactions_roots, trie_data_dicts, uncles_hashes = zip(*headers_bundle)
    transactions_bundles = tuple(zip(transactions_roots, trie_data_dicts))
    bodies_bundle = tuple(zip(bodies, transactions_bundles, uncles_hashes))
    validator = GetBlockBodiesValidator(headers)
    validator.validate_result(bodies_bundle)


def test_block_bodies_request_valid_with_partial_response():
    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, bodies, transactions_roots, trie_data_dicts, uncles_hashes = zip(*headers_bundle)
    transactions_bundles = tuple(zip(transactions_roots, trie_data_dicts))
    bodies_bundle = tuple(zip(bodies, transactions_bundles, uncles_hashes))
    validator = GetBlockBodiesValidator(headers)

    validator.validate_result(bodies_bundle[:2])
    validator.validate_result(bodies_bundle[2:])
    validator.validate_result((bodies_bundle[0], bodies_bundle[2], bodies_bundle[3]))


def test_block_bodies_request_with_fully_invalid_response():
    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, _, _, _, _ = zip(*headers_bundle)

    wrong_headers_bundle = mk_headers((3, 2), (4, 8), (1, 0), (0, 0))
    w_headers, w_bodies, w_transactions_roots, w_trie_data_dicts, w_uncles_hashes = zip(
        *wrong_headers_bundle
    )
    w_transactions_bundles = tuple(zip(w_transactions_roots, w_trie_data_dicts))
    w_bodies_bundle = tuple(zip(w_bodies, w_transactions_bundles, w_uncles_hashes))

    validator = GetBlockBodiesValidator(headers)
    with pytest.raises(ValidationError):
        validator.validate_result(w_bodies_bundle)


def test_block_bodies_request_with_extra_unrequested_bodies():
    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, bodies, transactions_roots, trie_data_dicts, uncles_hashes = zip(*headers_bundle)
    transactions_bundles = tuple(zip(transactions_roots, trie_data_dicts))
    bodies_bundle = tuple(zip(bodies, transactions_bundles, uncles_hashes))
    validator = GetBlockBodiesValidator(headers)

    wrong_headers_bundle = mk_headers((3, 2), (4, 8), (1, 0), (0, 0))
    w_headers, w_bodies, w_transactions_roots, w_trie_data_dicts, w_uncles_hashes = zip(
        *wrong_headers_bundle
    )
    w_transactions_bundles = tuple(zip(w_transactions_roots, w_trie_data_dicts))
    w_bodies_bundle = tuple(zip(w_bodies, w_transactions_bundles, w_uncles_hashes))

    validator = GetBlockBodiesValidator(headers)
    with pytest.raises(ValidationError):
        validator.validate_result(bodies_bundle + w_bodies_bundle)
