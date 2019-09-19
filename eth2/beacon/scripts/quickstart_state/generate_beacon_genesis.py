from pathlib import Path
import time

from eth2._utils.hash import hash_eth2
from eth2.beacon.genesis import initialize_beacon_state_from_eth1
from eth2.beacon.tools.builder.initializer import create_mock_deposits_and_root
from eth2.beacon.tools.fixtures.config_types import Minimal
from eth2.beacon.tools.fixtures.loading import load_config_at_path, load_yaml_at
from eth2.beacon.tools.misc.ssz_vector import override_lengths

ROOT_DIR = Path("eth2/beacon/scripts")
KEY_SET_FILE = Path("keygen_16_validators.yaml")


def _load_config(config):
    config_file_name = ROOT_DIR / Path(f"config_{config.name}.yaml")
    return load_config_at_path(config_file_name)


def _main():
    config_type = Minimal
    config = _load_config(config_type)
    override_lengths(config)

    key_set = load_yaml_at(ROOT_DIR / KEY_SET_FILE)

    pubkeys = ()
    privkeys = ()
    withdrawal_credentials = ()
    keymap = {}
    for key_pair in key_set:
        pubkey = key_pair["pubkey"].to_bytes(48, byteorder="big")
        privkey = key_pair["privkey"]
        withdrawal_credential = (
            config.BLS_WITHDRAWAL_PREFIX.to_bytes(1, byteorder="big")
            + hash_eth2(pubkey)[1:]
        )

        pubkeys += (pubkey,)
        privkeys += (privkey,)
        withdrawal_credentials += (withdrawal_credential,)
        keymap[pubkey] = privkey

    deposits, _ = create_mock_deposits_and_root(
        pubkeys, keymap, config, withdrawal_credentials
    )

    eth1_block_hash = b"\x42" * 32
    # NOTE: this timestamp is a placeholder
    eth1_timestamp = 10000
    state = initialize_beacon_state_from_eth1(
        eth1_block_hash=eth1_block_hash,
        eth1_timestamp=eth1_timestamp,
        deposits=deposits,
        config=config,
    )

    genesis_time = int(time.time())
    print(f"creating genesis at time {genesis_time}")
    genesis_state = state.copy(genesis_time=genesis_time)
    print(genesis_state.hash_tree_root.hex())


if __name__ == "__main__":
    _main()
