import asyncio
import os
from pathlib import Path
import tempfile
import uuid

from async_generator import (
    asynccontextmanager,
)
import pytest

from lahja import AsyncioEndpoint

from eth_utils import (
    decode_hex,
    to_canonical_address,
    to_wei,
)
from eth_keys import keys

from eth import constants as eth_constants
from eth.chains.base import (
    Chain,
    MiningChain
)
from eth.db.atomic import AtomicDB
# TODO: tests should not be locked into one set of VM rules.  Look at expanding
# to all mainnet vms.
from eth.vm.forks.spurious_dragon import SpuriousDragonVM

from lahja import (
    ConnectionConfig,
)

from trinity.config import (
    Eth1AppConfig,
    TrinityConfig,
)
from trinity.constants import (
    NETWORKING_EVENTBUS_ENDPOINT,
)
from trinity.chains.coro import (
    AsyncChainMixin,
)
from trinity.initialization import (
    ensure_eth1_dirs,
    initialize_data_dir,
)
from trinity.rpc.main import (
    RPCServer,
)
from trinity.rpc.modules import (
    initialize_eth1_modules,
)
from trinity.rpc.ipc import (
    IPCServer,
)
from trinity.tools.async_process_runner import (
    AsyncProcessRunner,
)
from trinity._utils.xdg import (
    get_xdg_trinity_root,
)
from trinity._utils.filesystem import (
    is_under_path,
)


def pytest_addoption(parser):
    parser.addoption("--enode", type=str, required=False)
    parser.addoption("--integration", action="store_true", default=False)
    parser.addoption("--fork", type=str, required=False)


class TestAsyncChain(Chain, AsyncChainMixin):
    pass


@pytest.fixture(autouse=True)
def xdg_trinity_root(monkeypatch, tmpdir):
    """
    Ensure proper test isolation as well as protecting the real directories.
    """
    trinity_root_dir = str(tmpdir.mkdir('t'))

    # The default path that pytest generates are too long to be allowed as
    # IPC Paths (hard UNIX rule). We are shorten them from something like:
    # /tmp/pytest-of-<username>/pytest-88/<test-name>_command1_0/trinity
    # to /tmp/pyt-<username>/88/<test-name>_command1_0/t

    fragment1 = 'pytest-of'
    fragment2 = 'pytest-'
    expected_fragments = (fragment1, fragment2)

    # If pytest ever changes the tmpdir generation layout, this breaks and we adapt
    is_expected_path = all(check_str in trinity_root_dir for check_str in expected_fragments)
    assert is_expected_path, f"Unexpected pytest tmp dir: {trinity_root_dir}, expected fragments: {expected_fragments}"  # noqa: E501

    trinity_root_dir = trinity_root_dir.replace(fragment1, 'pyt-').replace(fragment2, '')
    monkeypatch.setenv('XDG_TRINITY_ROOT', trinity_root_dir)

    assert not is_under_path(os.path.expandvars('$HOME'), get_xdg_trinity_root())

    return Path(trinity_root_dir)


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


# This fixture provides a tear down to run after each test that uses it.
# This ensures the AsyncProcessRunner will never leave a process behind
@pytest.fixture(scope="function")
def async_process_runner():
    runner = AsyncProcessRunner(
        # This allows running pytest with -s and observing the output
        debug_fn=lambda line: print(line)
    )
    yield runner
    try:
        runner.kill()
    except ProcessLookupError:
        pass


@asynccontextmanager
async def make_networking_event_bus():
    # Tests run concurrently, therefore we need unique IPC paths
    ipc_path = Path(f"networking-{uuid.uuid4()}.ipc")
    networking_connection_config = ConnectionConfig(
        name=NETWORKING_EVENTBUS_ENDPOINT,
        path=ipc_path
    )
    async with AsyncioEndpoint.serve(networking_connection_config) as endpoint:
        yield endpoint


@pytest.fixture
async def event_bus():
    async with make_networking_event_bus() as endpoint:
        yield endpoint


# Tests with multiple peers require us to give each of them there independent 'networking' endpoint
@pytest.fixture
async def other_event_bus():
    async with make_networking_event_bus() as endpoint:
        yield endpoint


@pytest.fixture(scope='session')
def jsonrpc_ipc_pipe_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / '{0}.ipc'.format(uuid.uuid4())


@pytest.fixture
def trinity_config():
    _trinity_config = TrinityConfig(network_id=1)
    initialize_data_dir(_trinity_config)
    return _trinity_config


@pytest.fixture
def eth1_app_config(trinity_config):
    eth1_app_config = Eth1AppConfig(trinity_config, None)
    ensure_eth1_dirs(eth1_app_config)
    return eth1_app_config


@pytest.fixture
def base_db():
    return AtomicDB()


@pytest.fixture
def funded_address_private_key():
    return keys.PrivateKey(
        decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8')
    )


@pytest.fixture
def funded_address(funded_address_private_key):
    return funded_address_private_key.public_key.to_canonical_address()


@pytest.fixture
def funded_address_initial_balance():
    return to_wei(1000, 'ether')


def _chain_with_block_validation(base_db, genesis_state, chain_cls=Chain):
    """
    Return a Chain object containing just the genesis block.

    The Chain's state includes one funded account, which can be found in the
    funded_address in the chain itself.

    This Chain will perform all validations when importing new blocks, so only
    valid and finalized blocks can be used with it. If you want to test
    importing arbitrarily constructe, not finalized blocks, use the
    chain_without_block_validation fixture instead.
    """
    genesis_params = {
        "bloom": 0,
        "coinbase": to_canonical_address("8888f1f195afa192cfee860698584c030f4c9db1"),
        "difficulty": 131072,
        "extra_data": b"B",
        "gas_limit": 3141592,
        "gas_used": 0,
        "mix_hash": decode_hex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"),
        "nonce": decode_hex("0102030405060708"),
        "block_number": 0,
        "parent_hash": decode_hex("0000000000000000000000000000000000000000000000000000000000000000"),  # noqa: E501
        "receipt_root": decode_hex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"),  # noqa: E501
        "timestamp": 1422494849,
        "transaction_root": decode_hex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"),  # noqa: E501
        "uncles_hash": decode_hex("1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347")  # noqa: E501
    }

    klass = chain_cls.configure(
        __name__='TestChain',
        vm_configuration=(
            (eth_constants.GENESIS_BLOCK_NUMBER, SpuriousDragonVM),
        ),
        chain_id=1337,
    )
    chain = klass.from_genesis(base_db, genesis_params, genesis_state)
    return chain


@pytest.fixture
def chain_with_block_validation(base_db, genesis_state):
    return _chain_with_block_validation(base_db, genesis_state, TestAsyncChain)


def import_block_without_validation(chain, block):
    return super(type(chain), chain).import_block(block, perform_validation=False)


@pytest.fixture
def base_genesis_state(funded_address, funded_address_initial_balance):
    return {
        funded_address: {
            'balance': funded_address_initial_balance,
            'nonce': 0,
            'code': b'',
            'storage': {},
        }
    }


@pytest.fixture
def genesis_state(base_genesis_state):
    return base_genesis_state


@pytest.fixture
def chain_without_block_validation(
        base_db,
        genesis_state):
    """
    Return a Chain object containing just the genesis block.

    This Chain does not perform any validation when importing new blocks.

    The Chain's state includes one funded account and a private key for it,
    which can be found in the funded_address and private_keys variables in the
    chain itself.
    """
    # Disable block validation so that we don't need to construct finalized blocks.
    overrides = {
        'import_block': import_block_without_validation,
        'validate_block': lambda self, block: None,
    }
    SpuriousDragonVMForTesting = SpuriousDragonVM.configure(validate_seal=lambda block: None)
    klass = MiningChain.configure(
        __name__='TestChainWithoutBlockValidation',
        vm_configuration=(
            (eth_constants.GENESIS_BLOCK_NUMBER, SpuriousDragonVMForTesting),
        ),
        chain_id=1337,
        **overrides,
    )
    genesis_params = {
        'block_number': eth_constants.GENESIS_BLOCK_NUMBER,
        'difficulty': eth_constants.GENESIS_DIFFICULTY,
        'gas_limit': 3141592,
        'parent_hash': eth_constants.GENESIS_PARENT_HASH,
        'coinbase': eth_constants.GENESIS_COINBASE,
        'nonce': eth_constants.GENESIS_NONCE,
        'mix_hash': eth_constants.GENESIS_MIX_HASH,
        'extra_data': eth_constants.GENESIS_EXTRA_DATA,
        'timestamp': 1501851927,
    }
    chain = klass.from_genesis(base_db, genesis_params, genesis_state)
    return chain


@pytest.mark.asyncio
@pytest.fixture
async def ipc_server(
        monkeypatch,
        event_bus,
        jsonrpc_ipc_pipe_path,
        event_loop,
        chain_with_block_validation):
    """
    This fixture runs a single RPC server over IPC over
    the course of all tests. It yields the IPC server only for monkeypatching purposes
    """
    rpc = RPCServer(
        initialize_eth1_modules(chain_with_block_validation, event_bus),
        chain_with_block_validation,
        event_bus,
    )
    ipc_server = IPCServer(rpc, jsonrpc_ipc_pipe_path, loop=event_loop)

    asyncio.ensure_future(ipc_server.run(), loop=event_loop)

    try:
        yield ipc_server
    finally:
        await ipc_server.cancel()
