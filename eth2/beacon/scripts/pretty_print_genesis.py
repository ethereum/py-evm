#!/usr/bin/env python

import argparse
from pathlib import Path
import sys

from ruamel.yaml import YAML
import ssz
from ssz.tools import to_formatted_dict

from eth2.beacon.tools.fixtures.loading import load_config_at_path
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.beacon.types.states import BeaconState


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-ssz", type=str, required=True)
    parser.add_argument("-config", type=str, required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    minimal_config = load_config_at_path(config_path)
    override_lengths(minimal_config)

    with open(args.ssz, "rb") as f:
        encoded = f.read()
    state = ssz.decode(encoded, sedes=BeaconState)

    yaml = YAML(typ="unsafe")
    yaml.dump(to_formatted_dict(state), sys.stdout)


if __name__ == "__main__":
    main()
