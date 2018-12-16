from eth.beacon.utils.hash import hash_
from eth_hash.auto import keccak


def test_hash():
    output = hash_(b'helloworld')
    assert len(output) == 32


def test_hash_is_keccak256():
    assert hash_(b'foo') == keccak(b'foo')
