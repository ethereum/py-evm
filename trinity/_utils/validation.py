import ipaddress
import re
from typing import (
    Any,
    Dict,
)
from urllib import parse as urlparse

from eth_utils import (
    is_address,
    decode_hex,
    ValidationError,
)

from eth_keys import (
    keys,
)

from eth.vm.base import (
    BaseVM,
)


FORBIDDEN_KEYS = {'v', 'r', 's', 'nonce'}
DERIVED_KEYS = {'from'}
RENAMED_KEYS = {'gas_price': 'gasPrice'}


def validate_transaction_gas_estimation_dict(transaction_dict: Dict[str, Any], vm: BaseVM) -> None:
    """Validate a transaction dictionary supplied for an RPC method call"""
    transaction_class = vm.get_transaction_class()

    all_keys = set(transaction_class._meta.field_names)
    allowed_keys = all_keys.difference(FORBIDDEN_KEYS).union(DERIVED_KEYS)
    spec_keys = set(RENAMED_KEYS.get(field_name, field_name) for field_name in allowed_keys)

    superfluous_keys = set(transaction_dict).difference(spec_keys)

    if superfluous_keys:
        raise ValueError(
            "The following invalid fields were given in a transaction: %r. Only %r are allowed" % (
                list(sorted(superfluous_keys)),
                list(sorted(spec_keys)),
            )
        )


def validate_transaction_call_dict(transaction_dict: Dict[str, Any], vm: BaseVM) -> None:
    validate_transaction_gas_estimation_dict(transaction_dict, vm)

    # 'to' is required in a call, but not a gas estimation
    if not is_address(transaction_dict.get('to', None)):
        raise ValueError("The 'to' field must be supplied when getting the result of a transaction")


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
