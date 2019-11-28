from pathlib import Path
from typing import Any, Dict

from eth_utils.toolz import assoc, keyfilter
from ruamel.yaml import YAML

from eth2.beacon.helpers import compute_epoch_at_slot
from eth2.configs import Eth2Config


def generate_config_by_dict(dict_config: Dict[str, Any]) -> Eth2Config:
    filtered_keys = (
        "DOMAIN_",
        "ETH1_FOLLOW_DISTANCE",
        "TARGET_AGGREGATORS_PER_COMMITTEE",
        "RANDOM_SUBNETS_PER_VALIDATOR",
        "EPOCHS_PER_RANDOM_SUBNET_SUBSCRIPTION",
        # Phase 1
        "MAX_EPOCHS_PER_CROSSLINK",
        "EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS",
        "EPOCHS_PER_CUSTODY_PERIOD",
        "CUSTODY_PERIOD_TO_RANDAO_PADDING",
        "SHARD_SLOTS_PER_BEACON_SLOT",
        "EPOCHS_PER_SHARD_PERIOD",
        "PHASE_1_FORK_EPOCH",
        "PHASE_1_FORK_SLOT",
    )

    return Eth2Config(
        **assoc(
            keyfilter(
                lambda name: all(key not in name for key in filtered_keys), dict_config
            ),
            "GENESIS_EPOCH",
            compute_epoch_at_slot(
                dict_config["GENESIS_SLOT"], dict_config["SLOTS_PER_EPOCH"]
            ),
        )
    )


def load_yaml_at(p: Path) -> Dict[str, Any]:
    y = YAML(typ="unsafe")
    return y.load(p)


config_cache: Dict[Path, Eth2Config] = {}


def load_config_at_path(p: Path) -> Eth2Config:
    if p in config_cache:
        return config_cache[p]

    config_data = load_yaml_at(p)
    config = generate_config_by_dict(config_data)
    config_cache[p] = config
    return config
