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

from py_ecc import bls

from ruamel.yaml import (
    YAML,
)

from ssz.tools import (
    from_formatted_dict,
)

from eth2.beacon.on_genesis import (
    get_genesis_block,
)
from eth2.beacon.state_machines.forks.xiao_long_bao import (
    XiaoLongBaoStateMachine,
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

# keymap
# <del>num_validators(should get it from CLI)</del>


root_dir = Path("/tmp/aaaa")

GENESIS_FILE = "genesis_state.yaml"


if TYPE_CHECKING:
    from ruamel.yaml.compat import StreamTextType  # noqa: F401


def extract_genesis_state_from_stream(stream: Union[Path, "StreamTextType"]) -> BeaconState:
    yaml = YAML(typ="unsafe")
    genesis_json = yaml.load(stream)
    state = from_formatted_dict(genesis_json, BeaconState)
    return state


def _extract_privkey_from_stream(stream: Union[Path, "StreamTextType"]) -> int:
    if isinstance(stream, Path):
        with stream.open('r') as f:
            return _extract_privkey_from_stream(stream=f)
    privkey_str = stream.read()
    return int(privkey_str, 10)


def extract_privkeys_from_dir(dir_path: Path) -> Dict[BLSPubkey, int]:
    validator_keymap = {}  # pub -> priv
    for key_file_name in os.listdir(dir_path):
        key_file_path = dir_path / key_file_name
        privkey = _extract_privkey_from_stream(key_file_path)
        validator_keymap[bls.privtopub(privkey)] = privkey
    return validator_keymap


if __name__ == "__main__":
    state = extract_genesis_state_from_stream(
        stream=root_dir / GENESIS_FILE,
    )
    block = get_genesis_block(
        genesis_state_root=state.root,
        genesis_slot=XIAO_LONG_BAO_CONFIG.GENESIS_SLOT,
        block_class=XiaoLongBaoStateMachine.block_class,
    )
    print(block)
    privkey = _extract_privkey_from_stream(root_dir / "keys" / "v0000000.privkey")
    print(privkey)
