#!/usr/bin/env python
import logging
from ruamel.yaml import (
    YAML,
)

from pathlib import Path

from eth2.beacon.state_machines.forks.serenity.state_transitions import (
    SerenityStateTransition,
)
import ssz
from eth2.beacon.state_machines.forks.skeleton_lake import MINIMAL_SERENITY_CONFIG
from eth2.beacon.tools.misc.ssz_vector import override_lengths

from eth2spec.fuzzing import decoder

from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.blocks import BeaconBlock

from eth2spec.phase0 import spec


def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')
    override_lengths(MINIMAL_SERENITY_CONFIG)

    with open('state_15.ssz', 'rb') as f:
        pre_state_encoded = f.read()
    pre_state = ssz.decode(pre_state_encoded, sedes=BeaconState)

    with open('block_16.ssz', 'rb') as f:
        block_encoded = f.read()
    pre_block = ssz.decode(block_encoded, sedes=BeaconBlock)

    trinity_post = trinity_transition(pre_state, pre_block)
    pyspec_post = pyspec_transition(pre_state, pre_block)

    for index in range(len(pyspec_post.balances)):
        assert trinity_post.balances[index] == pyspec_post.balances[index]

        if trinity_post.balances[index] == pyspec_post.balances[index]:
            continue
        print(
            f"trinity balances[{index}]: \t"
            f"{trinity_post.balances[index].to_bytes(8, 'big').hex()}"
        )
        print(
            f"pyspec balances[{index}]: \t"
            f"{pyspec_post.balances[index].to_bytes(8, 'big').hex()}"
        )

    print(f"trinity: {trinity_post.current_crosslinks[7]}")
    print(f"pyspec: {pyspec_post.current_crosslinks[7]}")


def trinity_transition(pre_state, pre_block):
    transition = SerenityStateTransition(MINIMAL_SERENITY_CONFIG)
    next_state = transition.apply_state_transition(
        pre_state, pre_block, 16, check_proposer_signature=True,
    )

    return next_state


def pyspec_transition(pre_state, pre_block):
    yaml = YAML(typ='base')
    loaded = yaml.load(Path('min.config.bak'))
    config_data = dict()
    for k, v in loaded.items():
        if v.startswith("0x"):
            config_data[k] = bytes.fromhex(v[2:])
        else:
            config_data[k] = int(v)

    spec.apply_constants_preset(config_data)

    spec_pre_state = decoder.translate_value(pre_state, spec.BeaconState)
    spec_pre_block = decoder.translate_value(pre_block, spec.BeaconBlock)

    spec_post_block = spec.state_transition(
        spec_pre_state, spec_pre_block, False
    )
    return spec_post_block


if __name__ == '__main__':
    main()
