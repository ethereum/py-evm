import re
import ipaddress

from urllib import parse as urlparse

from eth_utils import (
    decode_hex,
    ValidationError,
)

from eth_keys import (
    keys,
)


def validate_enode_uri(enode: str, require_ip: bool = False) -> None:
    try:
        parsed = urlparse.urlparse(enode)
    except ValueError as e:
        raise ValidationError(str(e))

    if parsed.scheme != 'enode' or not parsed.username:
        raise ValidationError('enode string must be of the form "enode://public-key@ip:port"')

    if not re.match('^[0-9a-fA-F]{128}$', parsed.username):
        raise ValidationError('public key must be a 128-character hex string')

    decoded_username = decode_hex(parsed.username)

    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError as e:
        raise ValidationError(str(e))

    if require_ip and ip in (ipaddress.ip_address('0.0.0.0'), ipaddress.ip_address('::')):
        raise ValidationError('A concrete IP address must be specified')

    keys.PublicKey(decoded_username)

    try:
        # this property performs a check that the port is in range
        parsed.port
    except ValueError as e:
        raise ValidationError(str(e))
