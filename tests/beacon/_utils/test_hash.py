from eth.beacon._utils.hash import (
    hash_eth2,
    repeat_hash_eth2,
)

from eth_hash.auto import keccak
from eth_typing import Hash32


def test_hash():
    output = hash_eth2(b'helloworld')
    assert len(output) == 32


def test_hash_is_keccak256():
    assert hash_eth2(b'foo') == keccak(b'foo')


def test_repeat_hash():
    output = repeat_hash_eth2(b'helloworld', 5)
    assert len(output) == 32


def test_repeat_hash_is_hash():
    assert repeat_hash_eth2(b'foo', 1) == hash_eth2(b'foo')


def test_repeat_hash_is_data():
    assert repeat_hash_eth2(b'bar', 0) == Hash32(b'bar')
