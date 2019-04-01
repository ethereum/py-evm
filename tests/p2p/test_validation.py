import pytest

from eth_utils import (
    ValidationError,
)

from p2p.validation import (
    validate_enode_uri
)


MALFORMED_URI = 'enode string must be of the form "enode://public-key@ip:port"'
GOOD_KEY = (
    '717ad99b1e67a93cd77806c9273d9195807da1db38ecfc535aa207598a4bd599'
    '645599a0d11f72c1107ba4fb44ab133b0188a2f0b47ff16ba12b0a5ec0350202'
)


@pytest.mark.parametrize(
    'uri,message',
    (
        ('/:hi', MALFORMED_URI),
        ('wrongscheme://public_key:[::]:30303', MALFORMED_URI),
        ('enode://public_key:[::]:30303', MALFORMED_URI),
        ('enode://nonhex@add', 'public key must be a 128-character hex string'),
        ('enode://00@[::]:30303', 'public key must be a 128-character hex string'),

        # The following tests check for validations which are done by functions internal
        # to validate_enode_uri
        (f'enode://{GOOD_KEY}@10:30303', "'10' does not appear to be an IPv4 or IPv6 address"),
        (f'enode://{GOOD_KEY}@[::]:3000000', "Port out of range 0-65535"),
        (f'enode://{GOOD_KEY}@[::/24]:30303', "Invalid IPv6 URL"),
    ),
)
def test_validate_enode_failures(uri, message):
    with pytest.raises(ValidationError, match=message):
        validate_enode_uri(uri)


@pytest.mark.parametrize(
    'uri',
    (
        (f'enode://{GOOD_KEY}@[::]:30303'),
        (f'enode://{GOOD_KEY}@[::]'),
        (f'enode://{GOOD_KEY}@10.0.1.2'),
        (f'enode://{GOOD_KEY}@10.0.1.2:5000'),
    ),
)
def test_validate_enode_success(uri):
    validate_enode_uri(uri)


@pytest.mark.parametrize(
    'uri,should_fail',
    (
        (f'enode://{GOOD_KEY}@[::]:30303', True),
        (f'enode://{GOOD_KEY}@[::]', True),
        (f'enode://{GOOD_KEY}@10.0.1.2', False),
        (f'enode://{GOOD_KEY}@10.0.1.2:5000', False),
    ),
)
def test_validate_enode_require_ip(uri, should_fail):
    if should_fail:
        message = "A concrete IP address must be specified"
        with pytest.raises(ValidationError, match=message):
            validate_enode_uri(uri, require_ip=True)
    else:
        validate_enode_uri(uri, require_ip=True)
