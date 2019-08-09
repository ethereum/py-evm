import importlib
import time

from eth2._utils.bls import bls

from eth2._utils.hash import (
    hash_eth2,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)
from eth2.beacon.tools.builder.initializer import (
    create_mock_genesis,
)

from trinity.config import (
    BeaconChainConfig,
    BeaconGenesisData,
)


bcc_helpers = importlib.import_module('tests.core.p2p-proto.bcc.helpers')


NUM_VALIDATORS = 8

privkeys = tuple(int.from_bytes(
    hash_eth2(str(i).encode('utf-8'))[:4], 'big')
    for i in range(NUM_VALIDATORS)
)
index_to_pubkey = {}
keymap = {}  # pub -> priv
for i, k in enumerate(privkeys):
    pubkey = bls.privtopub(k)
    index_to_pubkey[i] = pubkey
    keymap[pubkey] = k

genesis_state, genesis_block = create_mock_genesis(
    config=XIAO_LONG_BAO_CONFIG,
    pubkeys=keymap.keys(),
    keymap=keymap,
    genesis_block_class=SerenityBeaconBlock,
    genesis_time=int(time.time()),
)


def get_chain_from_genesis(db, indices):
    # pubkey -> privkey map
    validator_keymap = {
        index_to_pubkey[index]: keymap[index_to_pubkey[index]]
        for index in indices
    }
    genesis_data = BeaconGenesisData(
        genesis_time=genesis_state.genesis_time,
        state=genesis_state,
        validator_keymap=validator_keymap,
    )
    beacon_chain_config = BeaconChainConfig(chain_name='TestTestTest', genesis_data=genesis_data)
    chain_class = beacon_chain_config.beacon_chain_class
    return chain_class.from_genesis(
        base_db=db,
        genesis_state=genesis_state,
        genesis_block=genesis_block,
        genesis_config=beacon_chain_config.genesis_config,
    )
