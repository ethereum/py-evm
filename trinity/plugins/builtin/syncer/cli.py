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
    decode_hex,
    is_hex,
    to_int,
    remove_0x_prefix,
    ValidationError,
)

from trinity.sync.common.checkpoint import Checkpoint

from .etherscan_api import (
    get_block_by_number,
    get_latest_block,
)


def is_block_hash(value: str) -> bool:
    return is_hex(value) and len(remove_0x_prefix(value)) == 64


def remove_non_digits(value: str) -> str:
    return re.sub("\D", "", value)


def parse_checkpoint_uri(uri: str) -> Checkpoint:
    try:
        parsed = urllib.parse.urlparse(uri)
    except ValueError as e:
        raise ValidationError(str(e))

    path = parsed.path.lower()
    if path.startswith('/byhash'):
        return parse_byhash_uri(parsed)
    elif path == '/byetherscan/latest':
        return parse_byetherscan_uri(parsed)
    else:
        raise ValidationError("Not a valid checkpoint URI")


BLOCKS_FROM_TIP = 50


def parse_byetherscan_uri(parsed: urllib.parse.ParseResult) -> Checkpoint:

    latest_block_number = get_latest_block()
    checkpoint_block_number = latest_block_number - BLOCKS_FROM_TIP
    checkpoint_block_response = get_block_by_number(checkpoint_block_number)
    checkpoint_score = to_int(hexstr=checkpoint_block_response['totalDifficulty'])
    checkpoint_hash = checkpoint_block_response['hash']

    return Checkpoint(Hash32(decode_hex(checkpoint_hash)), checkpoint_score)


def parse_byhash_uri(parsed: urllib.parse.ParseResult) -> Checkpoint:
    scheme, netloc, query = parsed.scheme, parsed.netloc, parsed.query

    try:
        parsed_query = urllib.parse.parse_qsl(query)
    except ValueError as e:
        raise ValidationError(str(e))

    query_dict = dict(parsed_query)

    # we allow any kind of separator for a nicer UX. e.g. instead of "11487662456884849810705"
    # one can use "114 876 624 568 848 498 107 05" or "1,487,662,456,884,849,810,705". This also
    # allows copying out a value from e.g etherscan.
    score = remove_non_digits(query_dict.get('score', ''))

    parts = PurePosixPath(parsed.path).parts

    if len(parts) != 3 or scheme != 'eth' or netloc != 'block' or not score:
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
