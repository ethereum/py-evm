import asyncio
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from async_generator import (
    asynccontextmanager,
)
from cancel_token import OperationCancelled
from eth_keys import keys
from eth_utils import decode_hex
from eth_utils.toolz import (
    curry,
)

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
    enable_pow_mining,
    genesis,
    latest_mainnet_at,
)
from eth.db.header import HeaderDB
from eth.vm.forks.byzantium import ByzantiumVM
from eth.vm.forks.petersburg import PetersburgVM

from trinity.constants import TO_NETWORKING_BROADCAST_CONFIG
from trinity.db.base import BaseAsyncDB
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.db.eth1.header import BaseAsyncHeaderDB

from trinity.protocol.common.peer_pool_event_bus import (
    DefaultPeerPoolEventServer,
)
from trinity.protocol.eth.peer import (
    ETHProxyPeerPool,
)
from trinity.protocol.eth.servers import (
    ETHRequestServer,
)

ZIPPED_FIXTURES_PATH = Path(__file__).parent.parent / 'integration' / 'fixtures'


@curry
async def mock_request_response(request_type, response, bus):
    async for req in bus.stream(request_type):
        await bus.broadcast(response, req.broadcast_config())
        break


@curry
def run_mock_request_response(request_type, response, bus):
    asyncio.ensure_future(mock_request_response(request_type, response, bus))


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
    coro_exists = async_passthrough('exists')
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
    coro_get_canonical_head = async_passthrough('get_canonical_head')
    coro_import_block = coro_import_block
    coro_validate_chain = async_passthrough('validate_chain')
    coro_validate_receipt = async_passthrough('validate_receipt')


class FakeAsyncChain(MiningChain):
    coro_import_block = coro_import_block
    coro_get_block_header_by_hash = async_passthrough('get_block_header_by_hash')
    coro_get_canonical_head = async_passthrough('get_canonical_head')
    coro_validate_chain = async_passthrough('validate_chain')
    coro_validate_receipt = async_passthrough('validate_receipt')
    chaindb_class = FakeAsyncChainDB


class LatestTestChain(FakeAsyncChain):
    """
    A test chain that uses the most recent mainnet VM from block 0.
    That means the VM will explicitly change when a new network upgrade is locked in.
    """
    vm_configuration = ((0, PetersburgVM),)
    network_id = 999


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
        latest_mainnet_at(0),
        enable_pow_mining(),
        genesis(db=db, params=GENESIS_PARAMS, state=GENESIS_STATE),
    )


class DBFixture(Enum):
    twenty_pow_headers = '20pow_headers.ldb'
    thousand_pow_headers = '1000pow_headers.ldb'

    # this chain updates and churns storage, as well as creating a bunch of
    # contracts that are later deleted. It was built with:
    # build_pow_churning_fixture(db, 128)
    state_churner = 'churn_state.ldb'


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


@asynccontextmanager
async def run_peer_pool_event_server(event_bus, peer_pool, handler_type=None):

    handler_type = DefaultPeerPoolEventServer if handler_type is None else handler_type

    event_server = handler_type(
        event_bus,
        peer_pool,
        peer_pool.cancel_token
    )
    asyncio.ensure_future(event_server.run())

    await event_server.events.started.wait()
    try:
        yield event_server
    finally:
        await event_server.cancel()


@asynccontextmanager
async def run_request_server(event_bus, chaindb, server_type=None):
    server_type = ETHRequestServer if server_type is None else server_type
    request_server = server_type(
        event_bus,
        TO_NETWORKING_BROADCAST_CONFIG,
        chaindb,
    )
    asyncio.ensure_future(request_server.run())
    await request_server.events.started.wait()
    try:
        yield request_server
    finally:
        await request_server.cancel()


@asynccontextmanager
async def run_proxy_peer_pool(event_bus, peer_pool_type=None):

    peer_pool_type = ETHProxyPeerPool if peer_pool_type is None else peer_pool_type

    proxy_peer_pool = peer_pool_type(
        event_bus,
        TO_NETWORKING_BROADCAST_CONFIG,
    )
    asyncio.ensure_future(proxy_peer_pool.run())

    await proxy_peer_pool.events.started.wait()
    try:
        yield proxy_peer_pool
    finally:
        await proxy_peer_pool.cancel()
