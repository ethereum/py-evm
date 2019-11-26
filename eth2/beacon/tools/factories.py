import time
from typing import Any, Type

from eth.db.atomic import AtomicDB
import factory

from eth2.beacon.chains.base import BaseBeaconChain
from eth2.beacon.chains.testnet import SkeletonLakeChain
from eth2.beacon.state_machines.forks.serenity.blocks import SerenityBeaconBlock
from eth2.beacon.state_machines.forks.skeleton_lake.config import (
    MINIMAL_SERENITY_CONFIG,
)
from eth2.beacon.tools.builder.initializer import create_mock_genesis
from eth2.beacon.tools.builder.validator import mk_keymap_of_size
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.beacon.typing import Timestamp
from eth2.configs import Eth2GenesisConfig


class BeaconChainFactory(factory.Factory):
    num_validators = 8
    config = MINIMAL_SERENITY_CONFIG

    class Meta:
        model = SkeletonLakeChain

    @classmethod
    def _create(
        cls, model_class: Type[BaseBeaconChain], *args: Any, **kwargs: Any
    ) -> BaseBeaconChain:
        override_lengths(cls.config)

        keymap = mk_keymap_of_size(cls.num_validators)

        genesis_state, genesis_block = create_mock_genesis(
            config=cls.config,
            pubkeys=tuple(keymap.keys()),
            keymap=keymap,
            genesis_block_class=SerenityBeaconBlock,
            genesis_time=Timestamp(int(time.time())),
        )

        db = kwargs.pop("db", AtomicDB())
        chain = model_class.from_genesis(
            base_db=db,
            genesis_state=genesis_state,
            genesis_block=genesis_block,
            genesis_config=Eth2GenesisConfig(
                model_class.get_genesis_state_machine_class().config
            ),
        )

        return chain
