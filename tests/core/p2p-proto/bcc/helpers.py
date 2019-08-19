from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    merge,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth.db.atomic import AtomicDB

from eth2.beacon.types.blocks import (
    BeaconBlock,
    BeaconBlockBody,
)

from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth2.beacon.fork_choice.higher_slot import higher_slot_scoring
from eth2.beacon.state_machines.forks.serenity import SERENITY_CONFIG
from eth2.configs import (
    Eth2GenesisConfig,
)

from trinity.db.beacon.chain import AsyncBeaconChainDB

SERENITY_GENESIS_CONFIG = Eth2GenesisConfig(SERENITY_CONFIG)


def create_test_block(parent=None, genesis_config=SERENITY_GENESIS_CONFIG, **kwargs):
    defaults = {
        "slot": genesis_config.GENESIS_SLOT,
        "parent_root": ZERO_HASH32,
        "state_root": ZERO_HASH32,  # note: not the actual genesis state root
        "signature": EMPTY_SIGNATURE,
        "body": BeaconBlockBody(),
    }

    if parent is not None:
        kwargs["parent_root"] = parent.signing_root
        kwargs["slot"] = parent.slot + 1

    return BeaconBlock(**merge(defaults, kwargs))


@to_tuple
def create_branch(length, root=None, **start_kwargs):
    if length == 0:
        return

    if root is None:
        root = create_test_block()

    parent = create_test_block(parent=root, **start_kwargs)
    yield parent

    for _ in range(root.slot + 2, root.slot + length + 1):
        child = create_test_block(parent)
        yield child
        parent = child


async def get_chain_db(blocks=(),
                       genesis_config=SERENITY_GENESIS_CONFIG,
                       fork_choice_scoring=higher_slot_scoring):
    db = AtomicDB()
    chain_db = AsyncBeaconChainDB(db=db, genesis_config=genesis_config)
    await chain_db.coro_persist_block_chain(
        blocks,
        BeaconBlock,
        (higher_slot_scoring,) * len(blocks),
    )
    return chain_db


async def get_genesis_chain_db(genesis_config=SERENITY_GENESIS_CONFIG):
    genesis = create_test_block(genesis_config=genesis_config)
    return await get_chain_db((genesis,), genesis_config=genesis_config)
