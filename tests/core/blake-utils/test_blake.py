from eth.utils.blake import blake


def test_blake():
    output = blake(b'helloworld')
    assert len(output) == 32
    assert output == b'\xf2@\xa8\x02\x04\x1b_\xaf\x89E\x02\xd42I\xe0\x80\xd5\xd3\xf7\xe2\xd4Q\xf2\xcf\xc9;#|\xb5\xd2\xeeo'  # noqa: E501
