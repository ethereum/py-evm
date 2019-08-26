import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Sequence, Tuple, Type, Union

from eth_typing import BLSPubkey, BLSSignature
from eth_utils import decode_hex, to_tuple
from eth_utils.toolz import assoc, keyfilter
from ruamel.yaml import YAML
from ssz.tools import from_formatted_dict

from eth2.beacon.helpers import compute_epoch_of_slot
from eth2.beacon.tools.fixtures.config_name import ALL_CONFIG_NAMES, ConfigName
from eth2.beacon.tools.fixtures.test_case import OperationOrBlockHeader
from eth2.beacon.tools.fixtures.test_file import TestFile
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.states import BeaconState
from eth2.configs import Eth2Config


#
# Eth2Config
#
def generate_config_by_dict(dict_config: Dict[str, Any]) -> Eth2Config:
    config_without_domains = keyfilter(lambda name: "DOMAIN_" not in name, dict_config)
    config_without_phase_1 = keyfilter(
        lambda name: "EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS" not in name,
        config_without_domains,
    )

    return Eth2Config(
        **assoc(
            config_without_phase_1,
            "GENESIS_EPOCH",
            compute_epoch_of_slot(
                dict_config["GENESIS_SLOT"], dict_config["SLOTS_PER_EPOCH"]
            ),
        )
    )


config_cache: Dict[str, Eth2Config] = {}


def get_config(root_project_dir: Path, config_name: ConfigName) -> Eth2Config:
    if config_name in config_cache:
        return config_cache[config_name]

    # TODO: change the path after the constants presets are copied to submodule
    path = root_project_dir / "tests/eth2/fixtures"
    yaml = YAML(typ="unsafe")
    file_name = config_name + ".yaml"
    file_to_open = path / file_name
    with open(file_to_open, "U") as f:
        new_text = f.read()
        data = yaml.load(new_text)
    config = generate_config_by_dict(data)
    config_cache[config_name] = config
    return config


def get_test_file_from_dict(
    data: Dict[str, Any],
    root_project_dir: Path,
    file_name: str,
    parse_test_case_fn: Callable[..., Any],
) -> TestFile:
    config_name = data["config"]
    assert config_name in ALL_CONFIG_NAMES
    config_name = ConfigName(config_name)
    config = get_config(root_project_dir, config_name)
    handler = data["handler"]
    parsed_test_cases = tuple(
        parse_test_case_fn(test_case, handler, index, config)
        for index, test_case in enumerate(data["test_cases"])
    )
    return TestFile(file_name=file_name, config=config, test_cases=parsed_test_cases)


@to_tuple
def get_yaml_files_pathes(dir_path: Path) -> Iterable[str]:
    for root, _, files in os.walk(dir_path):
        for name in files:
            yield os.path.join(root, name)


@to_tuple
def load_from_yaml_files(
    root_project_dir: Path,
    dir_path: Path,
    config_names: Sequence[ConfigName],
    parse_test_case_fn: Callable[..., Any],
) -> Iterable[TestFile]:
    entries = get_yaml_files_pathes(dir_path)
    for file_path in entries:
        file_name = os.path.basename(file_path)
        if len(config_names) == 0:
            yield load_from_yaml_file(
                root_project_dir, file_path, file_name, parse_test_case_fn
            )
        for config_name in config_names:
            if config_name in file_name:
                yield load_from_yaml_file(
                    root_project_dir, file_path, file_name, parse_test_case_fn
                )


def load_from_yaml_file(
    root_project_dir: Path,
    file_path: str,
    file_name: str,
    parse_test_case_fn: Callable[..., Any],
) -> TestFile:
    yaml = YAML(typ="unsafe")
    with open(file_path, "U") as f:
        new_text = f.read()
        data = yaml.load(new_text)
        test_file = get_test_file_from_dict(
            data, root_project_dir, file_name, parse_test_case_fn
        )
        return test_file


@to_tuple
def get_all_test_files(
    root_project_dir: Path,
    fixture_pathes: Tuple[Path, ...],
    config_names: Sequence[ConfigName],
    parse_test_case_fn: Callable[..., Any],
) -> Iterable[TestFile]:
    for path in fixture_pathes:
        yield from load_from_yaml_files(
            root_project_dir, path, config_names, parse_test_case_fn
        )


#
# Parser helpers
#
def get_bls_setting(test_case: Dict[str, Any]) -> bool:
    # Default is free to choose, so we choose OFF.
    if "bls_setting" not in test_case or test_case["bls_setting"] == 2:
        return False
    else:
        return True


def get_states(
    test_case: Dict[str, Any], cls_state: Type[BeaconState]
) -> Tuple[BeaconState, BeaconState, bool]:
    pre = from_formatted_dict(test_case["pre"], cls_state)
    if test_case["post"] is not None:
        post = from_formatted_dict(test_case["post"], cls_state)
        is_valid = True
    else:
        post = None
        is_valid = False

    return pre, post, is_valid


def get_slots(test_case: Dict[str, Any]) -> int:
    return test_case["slots"] if "slots" in test_case else 0


def get_blocks(
    test_case: Dict[str, Any], cls_block: Type[BaseBeaconBlock]
) -> Tuple[BaseBeaconBlock, ...]:
    if "blocks" in test_case:
        return tuple(
            from_formatted_dict(block, cls_block) for block in test_case["blocks"]
        )
    else:
        return ()


def get_deposits(
    test_case: Dict[str, Any], cls_deposit: Type[Deposit]
) -> Tuple[Deposit, ...]:
    return tuple(
        from_formatted_dict(deposit, cls_deposit) for deposit in test_case["deposits"]
    )


def get_operation_or_header(
    test_case: Dict[str, Any],
    cls_operation_or_header: Type[OperationOrBlockHeader],
    handler: str,
) -> Tuple[OperationOrBlockHeader, ...]:
    if handler in test_case:
        return from_formatted_dict(test_case[handler], cls_operation_or_header)
    else:
        raise NameError(f"Operation {handler} is not supported.")


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


def get_input_sign_message(
    test_case: Dict[str, Any]
) -> Dict[str, Union[int, bytes, bytes]]:
    return {
        "privkey": int.from_bytes(decode_hex(test_case["input"]["privkey"]), "big"),
        "message_hash": decode_hex(test_case["input"]["message"]),
        "domain": decode_hex(test_case["input"]["domain"]),
    }


def get_output_bls_pubkey(test_case: Dict[str, Any]) -> BLSPubkey:
    return BLSPubkey(decode_hex(test_case["output"]))


def get_output_bls_signature(test_case: Dict[str, Any]) -> BLSSignature:
    return BLSSignature(decode_hex(test_case["output"]))
