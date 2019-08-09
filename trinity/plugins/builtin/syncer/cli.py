import argparse
from pathlib import PurePosixPath
import re
import urllib
from typing import (
    Any,
)

from eth_typing import (
    Hash32,
)

from eth_utils import (
    is_hex,
    remove_0x_prefix,
    decode_hex,
    ValidationError,
)

from trinity.sync.common.checkpoint import Checkpoint


def is_block_hash(value: str) -> bool:
    return is_hex(value) and len(remove_0x_prefix(value)) == 64


def remove_non_digits(value: str) -> str:
    return re.sub("\D", "", value)


def parse_checkpoint_uri(uri: str) -> Checkpoint:
    try:
        parsed = urllib.parse.urlparse(uri)
    except ValueError as e:
        raise ValidationError(str(e))

    scheme, netloc, path, query = parsed.scheme, parsed.netloc, parsed.path.lower(), parsed.query

    try:
        parsed_query = urllib.parse.parse_qsl(query)
    except ValueError as e:
        raise ValidationError(str(e))

    query_dict = dict(parsed_query)

    # we allow any kind of separator for a nicer UX. e.g. instead of "11487662456884849810705"
    # one can use "114 876 624 568 848 498 107 05" or "1,487,662,456,884,849,810,705". This also
    # allows copying out a value from e.g etherscan.
    score = remove_non_digits(query_dict.get('score', ''))

    is_by_hash = path.startswith('/byhash')
    parts = PurePosixPath(parsed.path).parts

    if len(parts) != 3 or scheme != 'eth' or netloc != 'block' or not is_by_hash or not score:
        raise ValidationError(
            'checkpoint string must be of the form'
            '"eth://block/byhash/<hash>?score=<score>"'
        )

    block_hash = parts[2]

    if not is_block_hash(block_hash):
        raise ValidationError(f'Block hash must be valid hex string, got: {block_hash}')

    if not score.isdigit():
        raise ValidationError(f'Score (total difficulty) must be an integer, got: {score}')

    return Checkpoint(Hash32(decode_hex(block_hash)), int(score))


class NormalizeCheckpointURI(argparse.Action):
    """
    Normalize the URI describing a sync checkpoint.
    """
    def __call__(self,
                 parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace,
                 value: Any,
                 option_string: str=None) -> None:
        parsed = parse_checkpoint_uri(value)
        setattr(namespace, self.dest, parsed)
