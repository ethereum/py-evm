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
)

from eth2._utils.bls import bls

from ruamel.yaml import (
    YAML,
)

from ssz.tools import (
    from_formatted_dict,
)

from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)
from eth2.beacon.tools.misc.ssz_vector import (
    override_vector_lengths,
)
from eth2.beacon.types.states import (
    BeaconState,
)

override_vector_lengths(XIAO_LONG_BAO_CONFIG)


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
    validator_keymap = {}  # pub -> priv
    for key_file_name in os.listdir(dir_path):
        key_file_path = dir_path / key_file_name
        privkey = _read_privkey(key_file_path)
        validator_keymap[bls.privtopub(privkey)] = privkey
    if len(validator_keymap) == 0:
        raise KeyFileNotFound("No validator key file is provided")
    return validator_keymap
