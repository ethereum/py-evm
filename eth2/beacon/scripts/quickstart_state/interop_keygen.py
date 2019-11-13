from pathlib import Path
from typing import Dict, Iterable

from eth_utils import encode_hex, int_to_big_endian, to_tuple
from ruamel.yaml import YAML

from eth2._utils.bls import bls
from eth2.beacon.tools.builder.initializer import generate_privkey_from_index

KEY_DIR = Path("eth2/beacon/scripts/quickstart_state")


def int_to_hex(n: int, byte_length: int = None) -> str:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b"\x00")
    return encode_hex(byte_value)


@to_tuple
def generate_validator_keypairs(validator_count: int) -> Iterable[Dict]:
    for index in range(validator_count):
        privkey = generate_privkey_from_index(index)
        yield {
            "privkey": int_to_hex(privkey),
            "pubkey": encode_hex(bls.privtopub(privkey)),
        }


if __name__ == "__main__":
    yaml = YAML(pure=True)
    yaml.default_flow_style = None
    n = 16
    keypairs = generate_validator_keypairs(n)
    key_file = KEY_DIR / Path(f"keygen_{n}_validators.yaml")

    with open(key_file, "w") as f:
        yaml.dump(keypairs, f)
