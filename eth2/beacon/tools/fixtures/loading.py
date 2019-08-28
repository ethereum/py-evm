from pathlib import Path
from typing import Any, Dict, Tuple, Union

from eth_typing import BLSPubkey, BLSSignature
from eth_utils import decode_hex
from eth_utils.toolz import assoc, keyfilter
from ruamel.yaml import YAML

from eth2.beacon.helpers import compute_epoch_of_slot
from eth2.configs import Eth2Config


def generate_config_by_dict(dict_config: Dict[str, Any]) -> Eth2Config:
    filtered_keys = ("DOMAIN_", "EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS")

    return Eth2Config(
        **assoc(
            keyfilter(
                lambda name: all(key not in name for key in filtered_keys), dict_config
            ),
            "GENESIS_EPOCH",
            compute_epoch_of_slot(
                dict_config["GENESIS_SLOT"], dict_config["SLOTS_PER_EPOCH"]
            ),
        )
    )


def _load_yaml_at(p: Path) -> Dict[str, Any]:
    y = YAML(typ="unsafe")
    return y.load(p)


# NOTE: should cache test suite data if users are running
# the same test suite at different points during testing.
def load_test_suite_at(p: Path) -> Dict[str, Any]:
    return _load_yaml_at(p)


config_cache: Dict[Path, Eth2Config] = {}


def load_config_at_path(p: Path) -> Eth2Config:
    if p in config_cache:
        return config_cache[p]

    config_data = _load_yaml_at(p)
    config = generate_config_by_dict(config_data)
    config_cache[p] = config
    return config


def get_input_bls_pubkeys(
    test_case: Dict[str, Any]
) -> Dict[str, Tuple[BLSPubkey, ...]]:
    return {
        "pubkeys": tuple(BLSPubkey(decode_hex(item)) for item in test_case["input"])
    }


def get_input_bls_signatures(
    test_case: Dict[str, Any]
) -> Dict[str, Tuple[BLSSignature, ...]]:
    return {
        "signatures": tuple(
            BLSSignature(decode_hex(item)) for item in test_case["input"]
        )
    }


def get_input_bls_privkey(test_case: Dict[str, Any]) -> Dict[str, int]:
    return {"privkey": int.from_bytes(decode_hex(test_case["input"]), "big")}


def get_input_sign_message(test_case: Dict[str, Any]) -> Dict[str, Union[int, bytes]]:
    return {
        "privkey": int.from_bytes(decode_hex(test_case["input"]["privkey"]), "big"),
        "message_hash": decode_hex(test_case["input"]["message"]),
        "domain": decode_hex(test_case["input"]["domain"]),
    }


def get_output_bls_pubkey(test_case: Dict[str, Any]) -> BLSPubkey:
    return BLSPubkey(decode_hex(test_case["output"]))


def get_output_bls_signature(test_case: Dict[str, Any]) -> BLSSignature:
    return BLSSignature(decode_hex(test_case["output"]))
