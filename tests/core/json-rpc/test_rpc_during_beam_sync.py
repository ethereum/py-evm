import asyncio
import json
import os
import pytest
import time
from typing import Dict

from async_generator import asynccontextmanager

from eth_hash.auto import keccak
from eth_utils.toolz import (
    assoc,
)
from eth_utils import (
    decode_hex,
    function_signature_to_4byte_selector,
    to_hex,
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
def chain(chain_without_block_validation):
    return chain_without_block_validation


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


@pytest.fixture
def fake_beam_syncer(chain, event_bus):
    @asynccontextmanager
    async def fake_beam_sync(removed_nodes: Dict):
        # beam sync starts, it fetches requested nodes from remote peers

        def replace_missing_node(missing_node_hash):
            if missing_node_hash not in removed_nodes:
                raise Exception(f'An unexpected node was requested: {missing_node_hash}')
            chain.chaindb.db[missing_node_hash] = removed_nodes.pop(missing_node_hash)

        async def collect_accounts(event: CollectMissingAccount):
            replace_missing_node(event.missing_node_hash)
            await event_bus.broadcast(
                MissingAccountCollected(1), event.broadcast_config()
            )
        accounts_sub = event_bus.subscribe(CollectMissingAccount, collect_accounts)

        async def collect_bytecodes(event: CollectMissingBytecode):
            replace_missing_node(event.bytecode_hash)
            await event_bus.broadcast(
                MissingBytecodeCollected(), event.broadcast_config()
            )
        bytecode_sub = event_bus.subscribe(CollectMissingBytecode, collect_bytecodes)

        async def collect_storage(event: CollectMissingStorage):
            replace_missing_node(event.missing_node_hash)
            await event_bus.broadcast(
                MissingStorageCollected(1), event.broadcast_config()
            )
        storage_sub = event_bus.subscribe(CollectMissingStorage, collect_storage)

        await event_bus.wait_until_any_endpoint_subscribed_to(CollectMissingAccount)
        await event_bus.wait_until_any_endpoint_subscribed_to(CollectMissingBytecode)
        await event_bus.wait_until_any_endpoint_subscribed_to(CollectMissingStorage)

        try:
            yield
        finally:
            accounts_sub.unsubscribe()
            bytecode_sub.unsubscribe()
            storage_sub.unsubscribe()

    return fake_beam_sync


# Test that eth_getBalance works during beam sync


@pytest.mark.asyncio
async def test_getBalance_during_beam_sync(
        chain, ipc_request, funded_address, funded_address_initial_balance,
        fake_beam_syncer):
    """
    Sanity check, if we call eth_getBalance we get back the expected response.
    """

    # sanity check, by default it works
    response = await ipc_request('eth_getBalance', [funded_address.hex(), 'latest'])
    assert 'error' not in response
    assert response['result'] == hex(funded_address_initial_balance)

    state_root_hash = chain.get_canonical_head().state_root
    state_root = chain.chaindb.db.pop(state_root_hash)

    # now that the hash is missing we should receive an error
    response = await ipc_request('eth_getBalance', [funded_address.hex(), 'latest'])
    assert 'error' in response
    assert response['error'].startswith('State trie database is missing node for hash')

    # with a beam syncer running it should work again! It sends requests to the syncer
    async with fake_beam_syncer({state_root_hash: state_root}):
        response = await ipc_request('eth_getBalance', [funded_address.hex(), 'latest'])
        assert 'error' not in response
        assert response['result'] == hex(funded_address_initial_balance)


@pytest.fixture
async def contract_code_hash(genesis_state, simple_contract_address):
    return keccak(genesis_state[simple_contract_address]['code'])


@pytest.mark.asyncio
async def test_getCode_during_beam_sync(
        chain, ipc_request, simple_contract_address, contract_code_hash,
        fake_beam_syncer):

    # sanity check, by default it works
    response = await ipc_request('eth_getCode', [simple_contract_address.hex(), 'latest'])
    assert 'error' not in response
    assert keccak(decode_hex(response['result'])) == contract_code_hash

    missing_bytecode = chain.chaindb.db.pop(contract_code_hash)

    # now that the hash is missing we should receive an error
    response = await ipc_request('eth_getCode', [simple_contract_address.hex(), 'latest'])
    assert 'error' in response
    assert response['error'].startswith('Database is missing bytecode for code hash')

    # with a beam syncer running it should work again! It sends requests to the syncer
    async with fake_beam_syncer({contract_code_hash: missing_bytecode}):
        response = await ipc_request('eth_getCode', [simple_contract_address.hex(), 'latest'])
        assert 'error' not in response
        assert keccak(decode_hex(response['result'])) == contract_code_hash


# Test that eth_getStorageAt works during Beam Sync


@pytest.fixture
def storage_root(chain, simple_contract_address):
    state_root = chain.get_canonical_head().state_root
    account_db = AccountDB(chain.chaindb.db, state_root)
    return account_db._get_storage_root(simple_contract_address)


@pytest.mark.asyncio
async def test_getStorageAt_during_beam_sync(
        ipc_request, simple_contract_address, storage_root, chain, fake_beam_syncer):

    params = [simple_contract_address.hex(), 1, 'latest']

    # sanity check, by default it works
    response = await ipc_request('eth_getStorageAt', params)
    assert 'error' not in response
    assert response['result'] == '0x01'  # this was set in the genesis_state fixture

    missing_node = chain.chaindb.db.pop(storage_root)

    # now that the hash is missing we should receive an error
    response = await ipc_request('eth_getStorageAt', params)
    assert 'error' in response
    assert response['error'].startswith('Storage trie database is missing hash')

    # with a beam syncer running it should work again! It sends requests to the syncer
    async with fake_beam_syncer({storage_root: missing_node}):
        response = await ipc_request('eth_getStorageAt', params)
        assert 'error' not in response
        assert response['result'] == '0x01'  # this was set in the genesis_state fixture


@pytest.fixture
def transaction(simple_contract_address):
    function_selector = function_signature_to_4byte_selector('getMeaningOfLife()')
    return {
        'from': '0x' + 'ff' * 20,  # unfunded address
        'to': to_hex(simple_contract_address),
        'gasPrice': to_hex(0),
        'data': to_hex(function_selector),
    }


@pytest.mark.asyncio
async def test_eth_call(
        ipc_request, contract_code_hash, chain, transaction, fake_beam_syncer):

    # sanity check, by default it works
    response = await ipc_request('eth_call', [transaction, 'latest'])
    assert 'error' not in response
    assert response['result'].endswith('002a')

    bytecode = chain.chaindb.db.pop(contract_code_hash)

    # now that the hash is missing we should receive an error
    response = await ipc_request('eth_call', [transaction, 'latest'])
    assert 'error' in response
    assert response['error'].startswith('Database is missing bytecode for code hash')

    # with a beam syncer running it should work again! It sends requests to the syncer
    async with fake_beam_syncer({contract_code_hash: bytecode}):
        response = await ipc_request('eth_call', [transaction, 'latest'])
        assert 'error' not in response
        assert response['result'].endswith('002a')


@pytest.mark.asyncio
async def test_eth_call_multiple_missing_nodes(
        ipc_request, contract_code_hash, storage_root,
        chain, transaction, fake_beam_syncer):

    state_root_hash = chain.get_canonical_head().state_root
    missing_nodes = {
        state_root_hash: chain.chaindb.db.pop(state_root_hash),
        contract_code_hash: chain.chaindb.db.pop(contract_code_hash),
        storage_root: chain.chaindb.db.pop(storage_root),
    }

    # now that the hash is missing we should receive an error
    response = await ipc_request('eth_call', [transaction, 'latest'])
    assert 'error' in response
    assert 'missing' in response['error']

    # with a beam syncer running it should work again! It sends requests to the syncer
    async with fake_beam_syncer(missing_nodes):
        response = await ipc_request('eth_call', [transaction, 'latest'])
        assert 'error' not in response
        assert response['result'].endswith('002a')


@pytest.mark.asyncio
async def test_eth_estimateGas(
        ipc_request, contract_code_hash, chain, transaction, fake_beam_syncer):

    # sanity check, by default it works
    response = await ipc_request('eth_estimateGas', [transaction, 'latest'])
    assert 'error' not in response
    assert response['result'] == '0x82a8'

    bytecode = chain.chaindb.db.pop(contract_code_hash)

    # now that the hash is missing we should receive an error
    response = await ipc_request('eth_estimateGas', [transaction, 'latest'])
    assert 'error' in response
    assert response['error'].startswith('Database is missing bytecode for code hash')

    # with a beam syncer running it should work again! It sends requests to the syncer
    async with fake_beam_syncer({contract_code_hash: bytecode}):
        response = await ipc_request('eth_estimateGas', [transaction, 'latest'])
        assert 'error' not in response
        assert response['result'] == '0x82a8'


@pytest.mark.asyncio
async def test_rpc_with_old_block(
        ipc_request, contract_code_hash, transaction, chain, fake_beam_syncer):
    response = await ipc_request('eth_estimateGas', [transaction, 'latest'])
    assert 'error' not in response
    assert response['result'] == '0x82a8'

    for _ in range(65):
        chain.mine_block()

    bytecode = chain.chaindb.db.pop(contract_code_hash)

    # if there is no beam syncer we return the original error
    response = await ipc_request('eth_estimateGas', [transaction, 'earliest'])
    assert 'error' in response
    assert response['error'].startswith('Database is missing bytecode for code hash')

    # if there is a beam syncer we return a more useful error
    async with fake_beam_syncer({contract_code_hash: bytecode}):
        response = await ipc_request('eth_estimateGas', [transaction, 'earliest'])
        assert 'error' in response
        assert response['error'].startswith('block "earliest" is too old to be fetched')
