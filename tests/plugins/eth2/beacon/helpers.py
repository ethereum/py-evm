from eth.db.atomic import AtomicDB

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.types.blocks import (
    BeaconBlock,
)

from trinity.db.beacon.chain import BaseAsyncBeaconChainDB

from tests.core.integration_test_helpers import (
    async_passthrough,
)
from eth.db.backends.base import (
    BaseAtomicDB,
)


# FIXME: borrowed from tests.core.p2p-proto.bcc. Failed to import it because its import path
#   contains hyphen.

class FakeAsyncBeaconChainDB(BaseAsyncBeaconChainDB, BeaconChainDB):

    def __init__(self, db: BaseAtomicDB) -> None:
        self.db = db

    coro_persist_block = async_passthrough('persist_block')
    coro_get_canonical_block_root = async_passthrough('get_canonical_block_root')
    coro_get_canonical_block_by_slot = async_passthrough('get_canonical_block_by_slot')
    coro_get_canonical_block_root_by_slot = async_passthrough('get_canonical_block_root_by_slot')
    coro_get_canonical_head = async_passthrough('get_canonical_head')
    coro_get_canonical_head_root = async_passthrough('get_canonical_head_root')
    coro_get_finalized_head = async_passthrough('get_finalized_head')
    coro_get_block_by_root = async_passthrough('get_block_by_root')
    coro_get_score = async_passthrough('get_score')
    coro_block_exists = async_passthrough('block_exists')
    coro_persist_block_chain = async_passthrough('persist_block_chain')
    coro_get_state_by_root = async_passthrough('get_state_by_root')
    coro_persist_state = async_passthrough('persist_state')
    coro_exists = async_passthrough('exists')
    coro_get = async_passthrough('get')


async def get_chain_db(blocks=()):
    db = AtomicDB()
    chain_db = FakeAsyncBeaconChainDB(db)
    await chain_db.coro_persist_block_chain(blocks, BeaconBlock)
    return chain_db
