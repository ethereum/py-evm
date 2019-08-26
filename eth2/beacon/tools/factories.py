import time
from typing import Any, Type, TypeVar

from eth.db.atomic import AtomicDB
import factory

from eth2._utils.bls import bls
from eth2._utils.hash import hash_eth2
from eth2.beacon.chains.base import BaseBeaconChain
from eth2.beacon.chains.testnet import TestnetChain
from eth2.beacon.state_machines.forks.serenity.blocks import SerenityBeaconBlock
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import XIAO_LONG_BAO_CONFIG
from eth2.beacon.tools.builder.initializer import create_mock_genesis
from eth2.beacon.typing import Timestamp
from eth2.configs import Eth2GenesisConfig

NUM_VALIDATORS = 8


privkeys = tuple(
    int.from_bytes(hash_eth2(str(i).encode("utf-8"))[:4], "big")
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
    pubkeys=tuple(keymap.keys()),
    keymap=keymap,
    genesis_block_class=SerenityBeaconBlock,
    genesis_time=Timestamp(int(time.time())),
)


TChain = TypeVar("TChain", bound=BaseBeaconChain)


class BeaconChainFactory(factory.Factory):
    class Meta:
        model = TestnetChain

    @classmethod
    def _create(cls, model_class: Type[TChain], *args: Any, **kwargs: Any) -> TChain:
        return model_class.from_genesis(
            base_db=AtomicDB(),
            genesis_state=genesis_state,
            genesis_block=genesis_block,
            genesis_config=Eth2GenesisConfig(
                model_class.get_genesis_state_machine_class().config
            ),
        )
