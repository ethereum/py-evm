import pytest

from eth_utils import encode_hex
from trinity.plugins.builtin.syncer.cli import (
    parse_checkpoint_uri,
    is_block_hash,
)

# This is just the score at the tip as it was at some point on August 26th 2019
# It serves as anchor so that we have *some* minimal expected score to test against.
MIN_EXPECTED_SCORE = 11631608640717612820968


@pytest.mark.parametrize(
    'uri',
    (
        'eth://block/byetherscan/latest',
    )
)
def test_parse_checkpoint(uri):
    checkpoint = parse_checkpoint_uri(uri)
    assert checkpoint.score >= MIN_EXPECTED_SCORE
    assert is_block_hash(encode_hex(checkpoint.block_hash))
