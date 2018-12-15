from eth.beacon.utils.hash import hash_


def test_hash():
    output = hash_(b'helloworld')
    assert len(output) == 32
