import asyncio
import json
import os
import pytest
import time

from eth_hash.auto import keccak
from eth_utils.toolz import (
    assoc,
)
from eth_utils import (
    decode_hex,
)

from eth.db.account import AccountDB

from trinity.sync.common.events import (
    CollectMissingAccount,
    CollectMissingBytecode,
    CollectMissingStorage,
    MissingAccountCollected,
    MissingBytecodeCollected,
    MissingStorageCollected,
)


def wait_for(path):
    for _ in range(100):
        if os.path.exists(path):
            return True
        time.sleep(0.01)
    return False


def build_request(method, params=None):
    if params is None:
        params = []
    request = {
        'jsonrpc': '2.0',
        'id': 3,
        'method': method,
        'params': params,
    }
    return json.dumps(request).encode()


def id_from_rpc_request(param):
    if isinstance(param, bytes):
        request = json.loads(param.decode())
        if 'method' in request and 'params' in request:
            rpc_params = (repr(p) for p in request['params'])
            return '%s(%s)' % (request['method'], ', '.join(rpc_params))
        else:
            return repr(param)
    else:
        return repr(param)


def can_decode_json(potential):
    try:
        json.loads(potential.decode())
        return True
    except json.decoder.JSONDecodeError:
        return False


async def get_ipc_response(
        jsonrpc_ipc_pipe_path,
        request_msg,
        event_loop,
        event_bus):

    # Give event subsriptions a moment to propagate.
    await asyncio.sleep(0.01)

    assert wait_for(jsonrpc_ipc_pipe_path), "IPC server did not successfully start with IPC file"

    reader, writer = await asyncio.open_unix_connection(str(jsonrpc_ipc_pipe_path), loop=event_loop)

    writer.write(request_msg)
    await writer.drain()
    result_bytes = b''
    while not can_decode_json(result_bytes):
        result_bytes += await asyncio.tasks.wait_for(reader.readuntil(b'}'), 0.25, loop=event_loop)

    writer.close()
    return json.loads(result_bytes.decode())


@pytest.fixture
def chain(chain_with_block_validation):
    return chain_with_block_validation


@pytest.fixture
def simple_contract_address():
    return b'\x88' * 20


@pytest.fixture
def genesis_state(base_genesis_state, simple_contract_address):
    """
    Includes runtime bytecode of compiled Solidity:

        pragma solidity ^0.4.24;

        contract GetValues {
            function getMeaningOfLife() public pure returns (uint256) {
                return 42;
            }
            function getGasPrice() public view returns (uint256) {
                return tx.gasprice;
            }
            function getBalance() public view returns (uint256) {
                return msg.sender.balance;
            }
            function doRevert() public pure {
                revert("always reverts");
            }
            function useLotsOfGas() public view {
                uint size;
                for (uint i = 0; i < 2**255; i++){
                    assembly {
                        size := extcodesize(0)
                    }
                }
            }
        }
    """
    return assoc(
        base_genesis_state,
        simple_contract_address,
        {
            'balance': 0,
            'nonce': 0,
            'code': decode_hex('60806040526004361061006c5763ffffffff7c010000000000000000000000000000000000000000000000000000000060003504166312065fe08114610071578063455259cb14610098578063858af522146100ad57806395dd7a55146100c2578063afc874d2146100d9575b600080fd5b34801561007d57600080fd5b506100866100ee565b60408051918252519081900360200190f35b3480156100a457600080fd5b506100866100f3565b3480156100b957600080fd5b506100866100f7565b3480156100ce57600080fd5b506100d76100fc565b005b3480156100e557600080fd5b506100d7610139565b333190565b3a90565b602a90565b6000805b7f80000000000000000000000000000000000000000000000000000000000000008110156101355760003b9150600101610100565b5050565b604080517f08c379a000000000000000000000000000000000000000000000000000000000815260206004820152600e60248201527f616c776179732072657665727473000000000000000000000000000000000000604482015290519081900360640190fd00a165627a7a72305820645df686b4a16d5a69fc6d841fc9ad700528c14b35ca5629e11b154a9d3dff890029'),  # noqa: E501
            'storage': {
                1: 1,
            },
        },
    )


@pytest.fixture
def ipc_request(jsonrpc_ipc_pipe_path, event_loop, event_bus, ipc_server):
    async def make_request(*args):
        request = build_request(*args)
        return await get_ipc_response(
            jsonrpc_ipc_pipe_path, request, event_loop, event_bus
        )
    return make_request


# Test that eth_getBalance works during beam sync


@pytest.mark.asyncio
async def test_get_balance_works(
        ipc_request, funded_address, funded_address_initial_balance):
    """
    Sanity check, if we call eth_getBalance we get back the expected response.
    """
    response = await ipc_request('eth_getBalance', [funded_address.hex(), 'latest'])
    assert 'error' not in response
    assert response['result'] == hex(funded_address_initial_balance)


@pytest.fixture
def missing_node(chain):
    state_root = chain.get_canonical_head().state_root
    return chain.chaindb.db.pop(state_root)


@pytest.mark.asyncio
async def test_fails_when_state_is_missing(ipc_request, funded_address, missing_node):
    """
    If the state root is missing then eth_getBalance throws an error.
    """
    response = await ipc_request('eth_getBalance', [funded_address.hex(), 'latest'])
    assert 'error' in response
    assert response['error'].startswith('State trie database is missing node for hash')


@pytest.mark.asyncio
async def test_missing_state_is_fetched_if_fetcher_exists(
        ipc_request, funded_address, funded_address_initial_balance,
        missing_node, chain, event_bus):

    # beam sync is not running, so we receive an error
    response = await ipc_request('eth_getBalance', [funded_address.hex(), 'latest'])
    assert 'error' in response
    assert response['error'].startswith('State trie database is missing node for hash')

    # beam sync starts, it fetches requested nodes from remote peers
    async def find_and_insert_node(event: CollectMissingAccount):
        state_root = chain.get_canonical_head().state_root
        chain.chaindb.db[state_root] = missing_node
        await event_bus.broadcast(MissingAccountCollected(1), event.broadcast_config())
    event_bus.subscribe(CollectMissingAccount, find_and_insert_node)
    await event_bus.wait_until_any_endpoint_subscribed_to(CollectMissingAccount)

    # beam sync fetches the missing node so no error is returned
    response = await ipc_request('eth_getBalance', [funded_address.hex(), 'latest'])
    assert 'error' not in response
    assert response['result'] == hex(funded_address_initial_balance)


# Test that eth_getCode works during beam sync


@pytest.fixture
async def contract_code_hash(genesis_state, simple_contract_address):
    return keccak(genesis_state[simple_contract_address]['code'])


@pytest.mark.asyncio
async def test_getCode(ipc_request, simple_contract_address, contract_code_hash):
    """
    Sanity check, if we call eth_getBalance we get back the expected response.
    """
    response = await ipc_request('eth_getCode', [simple_contract_address.hex(), 'latest'])
    assert 'error' not in response
    assert keccak(decode_hex(response['result'])) == contract_code_hash


@pytest.fixture
def missing_bytecode(chain, contract_code_hash):
    return chain.chaindb.db.pop(contract_code_hash)


@pytest.mark.asyncio
async def test_getCode_fails_when_state_is_missing(
        ipc_request, simple_contract_address, missing_bytecode):
    """
    If the state root is missing then eth_getBalance throws an error.
    """
    response = await ipc_request('eth_getCode', [simple_contract_address.hex(), 'latest'])
    assert 'error' in response
    assert response['error'].startswith('Database is missing bytecode for code hash')


@pytest.mark.asyncio
async def test_missing_code_is_fetched_if_fetcher_exists(
        ipc_request, simple_contract_address, contract_code_hash, missing_bytecode, chain,
        event_bus):

    # beam sync is not running, so we receive an error
    response = await ipc_request('eth_getCode', [simple_contract_address.hex(), 'latest'])
    assert 'error' in response
    assert response['error'].startswith('Database is missing bytecode for code hash')

    # beam sync starts, it fetches requested nodes from remote peers
    async def find_and_insert_node(event: CollectMissingBytecode):
        chain.chaindb.db[contract_code_hash] = missing_bytecode
        await event_bus.broadcast(MissingBytecodeCollected(), event.broadcast_config())
    event_bus.subscribe(CollectMissingBytecode, find_and_insert_node)
    await event_bus.wait_until_any_endpoint_subscribed_to(CollectMissingBytecode)

    # beam sync fetches the missing node so no error is returned
    response = await ipc_request('eth_getCode', [simple_contract_address.hex(), 'latest'])
    assert 'error' not in response
    assert keccak(decode_hex(response['result'])) == contract_code_hash


# Test that eth_getStorageAt works during Beam Sync


@pytest.mark.asyncio
async def test_getStorageAt(ipc_request, simple_contract_address):
    """
    Sanity check, if we call eth_getBalance we get back the expected response.
    """
    response = await ipc_request('eth_getStorageAt', [simple_contract_address.hex(), 1, 'latest'])
    assert 'error' not in response
    assert response['result'] == '0x01'  # this was set in the genesis_state fixture


@pytest.fixture
def storage_root(chain, simple_contract_address):
    state_root = chain.get_canonical_head().state_root
    account_db = AccountDB(chain.chaindb.db, state_root)
    return account_db._get_storage_root(simple_contract_address)


@pytest.fixture
def missing_storage_root(chain, storage_root):
    return chain.chaindb.db.pop(storage_root)


@pytest.mark.asyncio
async def test_missing_root_get_storage(ipc_request, simple_contract_address, missing_storage_root):
    """
    Sanity check, if we call eth_getBalance we get back the expected response.
    """
    response = await ipc_request('eth_getStorageAt', [simple_contract_address.hex(), 1, 'latest'])
    assert 'error' in response
    assert response['error'].startswith('Storage trie database is missing hash')


@pytest.mark.asyncio
async def test_missing_storage_is_fetched_if_fetcher_exists(
        ipc_request, simple_contract_address, storage_root, missing_storage_root, chain,
        event_bus):

    # beam sync is not running, so we receive an error
    response = await ipc_request('eth_getStorageAt', [simple_contract_address.hex(), 1, 'latest'])
    assert 'error' in response
    assert response['error'].startswith('Storage trie database is missing hash')

    # beam sync starts, it fetches requested nodes from remote peers
    async def find_and_insert_node(event: CollectMissingStorage):
        chain.chaindb.db[storage_root] = missing_storage_root
        await event_bus.broadcast(MissingStorageCollected(1), event.broadcast_config())
    event_bus.subscribe(CollectMissingStorage, find_and_insert_node)
    await event_bus.wait_until_any_endpoint_subscribed_to(CollectMissingStorage)

    # beam sync fetches the missing node so no error is returned
    response = await ipc_request('eth_getStorageAt', [simple_contract_address.hex(), 1, 'latest'])
    assert 'error' not in response
    assert response['result'] == '0x01'  # this was set in the genesis_state fixture
