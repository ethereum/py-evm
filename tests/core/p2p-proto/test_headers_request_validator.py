import pytest

from eth_utils import (
    ValidationError,
)

from trinity.protocol.common.requests import BaseHeaderRequest
from trinity.protocol.common.validators import BaseBlockHeadersValidator


FORWARD_0_to_5 = (0, 6, 0, False)
FORWARD_0_to_5_SKIP_1 = (0, 3, 1, False)

REVERSE_5_to_0 = (5, 6, 0, True)
REVERSE_5_to_0_SKIP_1 = (5, 3, 1, True)


BLOCK_HASH = b'\x01' * 32


class HeaderRequest(BaseHeaderRequest):
    max_size = 192

    def __init__(self,
                 block_number_or_hash,
                 max_headers,
                 skip,
                 reverse):
        self.block_number_or_hash = block_number_or_hash
        self.max_headers = max_headers
        self.skip = skip
        self.reverse = reverse


class BlockHeadersValidator(BaseBlockHeadersValidator):
    protocol_max_request_size = 192


@pytest.mark.parametrize(
    'block_number_or_hash,expected',
    (
        (0, True),
        (1, True),
        (10000000, True),
        (BLOCK_HASH, False),
    ),
)
def test_header_request_is_numbered_property(
        block_number_or_hash,
        expected):
    request = HeaderRequest(block_number_or_hash, 5, 0, False)
    assert request.is_numbered is expected


def test_header_request_generate_block_numbers_failure_A():
    """
    When using a hash-based request, the block number is required to
    be provided.
    """
    request = HeaderRequest(BLOCK_HASH, 5, 0, False)

    with pytest.raises(TypeError):
        request.generate_block_numbers()


def test_header_request_generate_block_numbers_failure_B():
    """
    When using a numbea-based request, the block number may not be
    provided.
    """
    request = HeaderRequest(0, 5, 0, False)

    with pytest.raises(TypeError):
        request.generate_block_numbers(1234)


def test_header_request_generate_block_numbers():
    """
    Simple smoke tests to be sure this works as expected.
    """
    request = HeaderRequest(0, 5, 0, False)

    assert request.generate_block_numbers() == (0, 1, 2, 3, 4)


def test_block_number_generation_limited_to_MAX_HEADERS_FETCH():
    request = HeaderRequest(0, 200, 0, False)

    assert request.generate_block_numbers() == tuple(range(192))


@pytest.mark.parametrize(
    "params,sequence",
    (
        (FORWARD_0_to_5, tuple()),
        (FORWARD_0_to_5, (0, 1, 2, 3, 4, 5)),
        (FORWARD_0_to_5, (0, 2, 4, 5)),
        (FORWARD_0_to_5, (0, 5)),
        (FORWARD_0_to_5, (2,)),
        (FORWARD_0_to_5, (0,)),
        (FORWARD_0_to_5, (5,)),
        # skips
        (FORWARD_0_to_5_SKIP_1, tuple()),
        (FORWARD_0_to_5_SKIP_1, (0, 2, 4)),
        (FORWARD_0_to_5_SKIP_1, (0, 4)),
        (FORWARD_0_to_5_SKIP_1, (2, 4)),
        (FORWARD_0_to_5_SKIP_1, (0, 2)),
        (FORWARD_0_to_5_SKIP_1, (0,)),
        (FORWARD_0_to_5_SKIP_1, (2,)),
        (FORWARD_0_to_5_SKIP_1, (4,)),
        # reverse
        (REVERSE_5_to_0, tuple()),
        (REVERSE_5_to_0, (5, 4, 3, 2, 1, 0)),
        (REVERSE_5_to_0, (5, 4, 3)),
        (REVERSE_5_to_0, (2, 1, 0)),
    ),
)
def test_header_request_sequence_matching(params, sequence):
    validator = BlockHeadersValidator(*params)

    validator._validate_sequence(sequence)


@pytest.mark.parametrize(
    "params,sequence",
    (
        (FORWARD_0_to_5, (0, 0, 1, 2, 3, 4, 5)),
        (FORWARD_0_to_5, (0, 1, 2, 2, 3, 4, 5)),
        (FORWARD_0_to_5, (0, 1, 2, 3, 4, 5, 5)),
    ),
)
def test_header_request_sequence_matching_duplicate(params, sequence):
    validator = BlockHeadersValidator(*params)

    with pytest.raises(ValidationError, match="Duplicate"):
        validator._validate_sequence(sequence)


@pytest.mark.parametrize(
    "params,sequence",
    (
        (FORWARD_0_to_5, (0, 1, 2, 3, 4, 5, 6)),
        (FORWARD_0_to_5, (0, 1, 3, 5, 6)),
        (FORWARD_0_to_5_SKIP_1, (0, 2, 4, 6)),
        (FORWARD_0_to_5_SKIP_1, (0, 2, 3, 4)),
        (FORWARD_0_to_5_SKIP_1, (0, 2, 3)),
    ),
)
def test_header_request_sequence_matching_unexpected(params, sequence):
    validator = BlockHeadersValidator(*params)

    with pytest.raises(ValidationError, match="unexpected headers"):
        validator._validate_sequence(sequence)


@pytest.mark.parametrize(
    "params,sequence",
    (
        (FORWARD_0_to_5, (0, 1, 3, 2, 4, 5)),
        (FORWARD_0_to_5, (0, 1, 5, 3)),
        (FORWARD_0_to_5_SKIP_1, (0, 4, 2)),
        (FORWARD_0_to_5_SKIP_1, (2, 0, 4)),
    ),
)
def test_header_request_sequence_matching_wrong_order(params, sequence):
    validator = BlockHeadersValidator(*params)

    with pytest.raises(ValidationError, match="incorrectly ordered"):
        validator._validate_sequence(sequence)
