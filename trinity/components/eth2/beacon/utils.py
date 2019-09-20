import logging
import os
from pathlib import (
    Path,
)
from typing import (
    Dict,
    TYPE_CHECKING,
    Union,
)

from eth_typing import (
    BLSPubkey,
    Hash32,
)

from eth2._utils.bls import bls

from ruamel.yaml import (
    YAML,
)

from ssz.tools import (
    from_formatted_dict,
)

from eth2.beacon.state_machines.forks.skeleton_lake.config import (
    MINIMAL_SERENITY_CONFIG
)
from eth2.beacon.tools.misc.ssz_vector import (
    override_lengths,
)
from eth2.beacon.types.states import (
    BeaconState,
)
from eth_utils import humanize_hash

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

override_lengths(MINIMAL_SERENITY_CONFIG)

if TYPE_CHECKING:
    from ruamel.yaml.compat import StreamTextType  # noqa: F401


class KeyFileNotFound(FileNotFoundError):
    pass


def extract_genesis_state_from_stream(stream: Union[Path, "StreamTextType"]) -> BeaconState:
    yaml = YAML(typ="unsafe")
    genesis_json = yaml.load(stream)
    state = from_formatted_dict(genesis_json, BeaconState)
    return state


def _read_privkey(stream: Union[Path, "StreamTextType"]) -> int:
    if isinstance(stream, Path):
        with stream.open('r') as f:
            return _read_privkey(stream=f)
    privkey_str = stream.read()
    return int(privkey_str, 10)


def extract_privkeys_from_dir(dir_path: Path) -> Dict[BLSPubkey, int]:
    validator_keymap: Dict[BLSPubkey, int] = {}  # pub -> priv
    try:
        key_files = os.listdir(dir_path)
    except FileNotFoundError:
        logger.debug('Could not find key directory: %s', str(dir_path))
        return validator_keymap
    for key_file_name in key_files:
        key_file_path = dir_path / key_file_name
        privkey = _read_privkey(key_file_path)
        pubkey = bls.privtopub(privkey)
        validator_keymap[pubkey] = privkey
        logger.debug('imported public key: %s', humanize_hash(Hash32(pubkey)))
    if len(validator_keymap) == 0:
        pass
    return validator_keymap
