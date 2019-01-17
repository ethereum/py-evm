import asyncio
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from cancel_token import OperationCancelled
from eth_keys import keys
from eth_utils import decode_hex

from eth import MainnetChain, RopstenChain, constants
from eth.chains.base import (
    MiningChain,
)
from eth.db.backends.level import LevelDB
from eth.db.backends.memory import MemoryDB
from eth.db.atomic import AtomicDB
from eth.db.chain import ChainDB
from eth.tools.builder.chain import (
    build,
    byzantium_at,
    enable_pow_mining,
    genesis,
)
from eth.db.header import HeaderDB
from eth.vm.forks.byzantium import ByzantiumVM

from trinity.db.base import BaseAsyncDB
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.db.eth1.header import BaseAsyncHeaderDB

ZIPPED_FIXTURES_PATH = Path(__file__).parent.parent / 'integration' / 'fixtures'


async def connect_to_peers_loop(peer_pool, nodes):
    """Loop forever trying to connect to one of the given nodes if the pool is not yet full."""
    while peer_pool.is_operational:
        try:
            if not peer_pool.is_full:
                await peer_pool.connect_to_nodes(nodes)
            await peer_pool.wait(asyncio.sleep(2))
        except OperationCancelled:
            break


def async_passthrough(base_name):
    coro_name = 'coro_{0}'.format(base_name)

    async def passthrough_method(self, *args, **kwargs):
        return getattr(self, base_name)(*args, **kwargs)
    passthrough_method.__name__ = coro_name
    return passthrough_method


class FakeAsyncAtomicDB(AtomicDB, BaseAsyncDB):
    coro_set = async_passthrough('set')
    coro_exists = async_passthrough('exists')


class FakeAsyncMemoryDB(MemoryDB, BaseAsyncDB):
    coro_set = async_passthrough('set')
    coro_exists = async_passthrough('exists')


class FakeAsyncLevelDB(LevelDB, BaseAsyncDB):
    coro_set = async_passthrough('set')
    coro_exists = async_passthrough('exists')


class FakeAsyncHeaderDB(BaseAsyncHeaderDB, HeaderDB):
    coro_get_canonical_block_hash = async_passthrough('get_canonical_block_hash')
    coro_get_canonical_block_header_by_number = async_passthrough('get_canonical_block_header_by_number')  # noqa: E501
    coro_get_canonical_head = async_passthrough('get_canonical_head')
    coro_get_block_header_by_hash = async_passthrough('get_block_header_by_hash')
    coro_get_score = async_passthrough('get_score')
    coro_header_exists = async_passthrough('header_exists')
    coro_persist_header = async_passthrough('persist_header')
    coro_persist_header_chain = async_passthrough('persist_header_chain')


class FakeAsyncChainDB(BaseAsyncChainDB, FakeAsyncHeaderDB, ChainDB):
    coro_persist_block = async_passthrough('persist_block')
    coro_persist_uncles = async_passthrough('persist_uncles')
    coro_persist_trie_data_dict = async_passthrough('persist_trie_data_dict')
    coro_get = async_passthrough('get')
    coro_get_block_transactions = async_passthrough('get_block_transactions')
    coro_get_block_uncles = async_passthrough('get_block_uncles')
    coro_get_receipts = async_passthrough('get_receipts')


async def coro_import_block(chain, block, perform_validation=True):
    # Be nice and yield control to give other coroutines a chance to run before us as
    # importing a block is a very expensive operation.
    await asyncio.sleep(0)
    return chain.import_block(block, perform_validation=perform_validation)


class FakeAsyncRopstenChain(RopstenChain):
    chaindb_class = FakeAsyncChainDB
    coro_import_block = coro_import_block
    coro_validate_chain = async_passthrough('validate_chain')
    coro_validate_receipt = async_passthrough('validate_receipt')


class FakeAsyncMainnetChain(MainnetChain):
    chaindb_class = FakeAsyncChainDB
    coro_import_block = coro_import_block
    coro_validate_chain = async_passthrough('validate_chain')
    coro_validate_receipt = async_passthrough('validate_receipt')


class FakeAsyncChain(MiningChain):
    coro_import_block = coro_import_block
    coro_validate_chain = async_passthrough('validate_chain')
    coro_validate_receipt = async_passthrough('validate_receipt')
    chaindb_class = FakeAsyncChainDB


class ByzantiumTestChain(FakeAsyncChain):
    vm_configuration = ((0, ByzantiumVM),)
    network_id = 999


FUNDED_ACCT = keys.PrivateKey(
    decode_hex("49a7b37aa6f6645917e7b807e9d1c00d4fa71f18343b0d4122a4d2df64dd6fee"))


def load_mining_chain(db):
    GENESIS_PARAMS = {
        'coinbase': constants.ZERO_ADDRESS,
        'difficulty': 5,
        'gas_limit': 3141592,
        'timestamp': 1514764800,
    }

    GENESIS_STATE = {
        FUNDED_ACCT.public_key.to_canonical_address(): {
            "balance": 100000000000000000,
        }
    }

    return build(
        FakeAsyncChain,
        byzantium_at(0),
        enable_pow_mining(),
        genesis(db=db, params=GENESIS_PARAMS, state=GENESIS_STATE),
    )


class DBFixture(Enum):
    twenty_pow_headers = '20pow_headers.ldb'
    thousand_pow_headers = '1000pow_headers.ldb'


def load_fixture_db(db_fixture, db_class=LevelDB):
    """
    Extract the database from the zip file to a temp directory, which has two benefits and one cost:
    - B1. works with xdist, multiple access to the ldb files at the same time
    - B2. prevents dirty-ing the git index
    - C1. slows down test, because of time to extract files
    """
    assert isinstance(db_fixture, DBFixture)
    zipped_path = ZIPPED_FIXTURES_PATH / f"{db_fixture.value}.zip"

    with ZipFile(zipped_path, 'r') as zipped, TemporaryDirectory() as tmpdir:
        zipped.extractall(tmpdir)
        yield db_class(Path(tmpdir) / db_fixture.value)
