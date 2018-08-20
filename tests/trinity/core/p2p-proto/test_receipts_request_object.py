import os
import time

import pytest

from eth_utils import (
    to_tuple,
    ValidationError,
)

from eth.db.trie import make_trie_root_and_nodes
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt

from trinity.protocol.eth.validators import ReceiptsValidator


@to_tuple
def mk_receipts(num_receipts):
    for _ in range(num_receipts):
        yield Receipt(
            state_root=os.urandom(32),
            gas_used=21000,
            bloom=0,
            logs=[],
        )


def mk_header_and_receipts(block_number, num_receipts):
    receipts = mk_receipts(num_receipts)
    root_hash, trie_root_and_data = make_trie_root_and_nodes(receipts)
    header = BlockHeader(
        difficulty=1000000,
        block_number=block_number,
        gas_limit=3141592,
        timestamp=int(time.time()),
        receipt_root=root_hash,
    )
    return header, receipts, (root_hash, trie_root_and_data)


@to_tuple
def mk_headers(*counts):
    for idx, num_receipts in enumerate(counts, 1):
        yield mk_header_and_receipts(idx, num_receipts)


def test_receipts_request_empty_response_is_valid():
    headers_bundle = mk_headers(1, 3, 2, 5, 4)
    headers, _, _ = zip(*headers_bundle)
    validator = ReceiptsValidator(headers)
    validator.validate_result(tuple())


def test_receipts_request_valid_with_full_response():
    headers_bundle = mk_headers(1, 3, 2, 5, 4)
    headers, receipts, trie_roots_and_data = zip(*headers_bundle)
    receipts_bundle = tuple(zip(receipts, trie_roots_and_data))
    validator = ReceiptsValidator(headers)
    validator.validate_result(receipts_bundle)


def test_receipts_request_valid_with_partial_response():
    headers_bundle = mk_headers(1, 3, 2, 5, 4)
    headers, receipts, trie_roots_and_data = zip(*headers_bundle)
    receipts_bundle = tuple(zip(receipts, trie_roots_and_data))
    validator = ReceiptsValidator(headers)

    validator.validate_result(receipts_bundle[:3])

    validator.validate_result(receipts_bundle[2:])

    validator.validate_result((receipts_bundle[1], receipts_bundle[3], receipts_bundle[4]))


def test_receipts_request_with_fully_invalid_response():
    headers_bundle = mk_headers(1, 3, 2, 5, 4)
    headers, _, _ = zip(*headers_bundle)

    wrong_headers = mk_headers(4, 3, 8)
    _, wrong_receipts, wrong_trie_roots_and_data = zip(*wrong_headers)
    receipts_bundle = tuple(zip(wrong_receipts, wrong_trie_roots_and_data))

    validator = ReceiptsValidator(headers)

    with pytest.raises(ValidationError):
        validator.validate_result(receipts_bundle)


def test_receipts_request_with_extra_unrequested_receipts():
    headers_bundle = mk_headers(1, 3, 2, 5, 4)
    headers, receipts, trie_roots_and_data = zip(*headers_bundle)
    receipts_bundle = tuple(zip(receipts, trie_roots_and_data))

    wrong_headers = mk_headers(4, 3, 8)
    _, wrong_receipts, wrong_trie_roots_and_data = zip(*wrong_headers)
    extra_receipts_bundle = tuple(zip(wrong_receipts, wrong_trie_roots_and_data))

    validator = ReceiptsValidator(headers)

    with pytest.raises(ValidationError):
        validator.validate_result(receipts_bundle + extra_receipts_bundle)
