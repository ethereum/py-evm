import importlib

from py_ecc import bls

from trinity.config import (
    BeaconChainConfig,
    BeaconGenesisData,
)

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

helpers = importlib.import_module('tests.core.p2p-proto.bcc.helpers')


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
    num_validators=NUM_VALIDATORS,
    config=XIAO_LONG_BAO_CONFIG,
    keymap=keymap,
    genesis_block_class=SerenityBeaconBlock,
    genesis_time=0,
)
genesis_data = BeaconGenesisData(
    genesis_time=0,
    genesis_slot=XIAO_LONG_BAO_CONFIG.GENESIS_SLOT,
    keymap=keymap,
    num_validators=NUM_VALIDATORS,
)
beacon_chain_config = BeaconChainConfig(chain_name='TestTestTest', genesis_data=genesis_data)
chain_class = beacon_chain_config.beacon_chain_class
