import asyncio
import json
import os
import pytest
import time
import uuid

from eth._utils.address import (
    force_bytes_to_address,
)
from eth_utils.toolz import (
    assoc,
)
from eth_utils import (
    decode_hex,
    function_signature_to_4byte_selector,
    to_bytes,
    to_hex,
    to_int,
)

from trinity.nodes.events import (
    NetworkIdRequest,
    NetworkIdResponse,
)
from trinity.protocol.common.events import (
    ConnectToNodeCommand,
    PeerCountRequest,
    PeerCountResponse,
)
from trinity.sync.common.events import (
    SyncingRequest,
    SyncingResponse,
)
from trinity.sync.common.types import (
    SyncProgress
)

from trinity._utils.version import construct_trinity_client_identifier

from tests.core.integration_test_helpers import (
    mock_request_response,
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


def transfer_eth(chain, sender_private_key, value, to):
    tx = chain.create_unsigned_transaction(
        nonce=0,
        gas_price=1,
        gas=3138525,
        data=uuid.uuid4().bytes,
        to=to,
        value=value
    ).as_signed_transaction(sender_private_key)
    chain.apply_transaction(tx)
    chain.mine_block()


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
            'storage': {},
        },
    )


def uint256_to_bytes(uint):
    return to_bytes(uint).rjust(32, b'\0')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'request_msg, expected',
    (
        (
            b'{}',
            {'error': "Invalid Request: empty"},
        ),
        (
            build_request('notamethod'),
            {'error': "Invalid RPC method: 'notamethod'", 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('eth_accounts'),
            {'result': [], 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('eth_mining'),
            {'result': False, 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('eth_coinbase'),
            {'result': '0x0000000000000000000000000000000000000000', 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('eth_hashrate'),
            {'result': '0x0', 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('web3_clientVersion'),
            {'result': construct_trinity_client_identifier(), 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('web3_sha3', ['0x89987239849872']),
            {
                'result': '0xb3406131994d9c859de3c4400e12f630638e1e992c6453358c16d0e6ce2b1a70',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
        (
            build_request('web3_sha3', ['0x']),
            {
                'result': '0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
        (
            build_request('net_listening'),
            {'result': True, 'id': 3, 'jsonrpc': '2.0'},
        ),
    ),
)
async def test_ipc_requests(
        jsonrpc_ipc_pipe_path,
        request_msg,
        expected,
        event_loop,
        event_bus,
        ipc_server):
    result = await get_ipc_response(jsonrpc_ipc_pipe_path, request_msg, event_loop, event_bus)
    assert result == expected


@pytest.mark.asyncio
async def test_network_id_ipc_request(
        jsonrpc_ipc_pipe_path,
        event_loop,
        event_bus,
        ipc_server):

    asyncio.ensure_future(
        mock_request_response(NetworkIdRequest, NetworkIdResponse(1337))(event_bus))
    request_msg = build_request('net_version')
    expected = {'result': '1337', 'id': 3, 'jsonrpc': '2.0'}
    result = await get_ipc_response(jsonrpc_ipc_pipe_path, request_msg, event_loop, event_bus)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'request_msg, expected',
    (
        (
            # simple transaction, with all fields inferred
            # (except 'to', which must be provided when not creating a contract)
            build_request('eth_estimateGas', params=[{'to': '0x' + '00' * 20}, 'latest']),
            # simple transactions are correctly identified as 21000 gas during estimation
            {'result': hex(21000), 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            # test block number
            build_request('eth_estimateGas', params=[{'to': '0x' + '00' * 20}, '0x0']),
            {'result': hex(21000), 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            # another simple transaction, with all fields provided
            build_request('eth_estimateGas', params=[{
                'to': '0x' + '00' * 20,
                'from': '0x' + '11' * 20,
                'gasPrice': '0x2',
                'gas': '0x3',
                'value': '0x0',
                'data': '0x',
            }, 'latest']),
            {'result': hex(21000), 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            # try adding garbage data to increase estimate
            build_request('eth_estimateGas', params=[{
                'to': '0x' + '00' * 20,
                'data': '0x01',
            }, 'latest']),
            {'result': hex(21068), 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            # deploy a tiny contract
            build_request('eth_estimateGas', params=[{
                'data': '0x3838533838f3',
            }, 'latest']),
            {'result': hex(65459), 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            # specifying v,r,s is invalid
            build_request('eth_estimateGas', params=[{
                'v': '0x' + '00' * 20,
                'r': '0x' + '00' * 20,
                's': '0x' + '00' * 20,
            }, 'latest']),
            {
                'error': "The following invalid fields were given in a transaction: ['r', 's', 'v']. Only ['data', 'from', 'gas', 'gasPrice', 'to', 'value'] are allowed",  # noqa: E501
                'id': 3,
                'jsonrpc': '2.0',
            }
        ),
        (
            # specifying gas_price is invalid
            build_request('eth_estimateGas', params=[{
                'gas_price': '0x0',
            }, 'latest']),
            {
                'error': "The following invalid fields were given in a transaction: ['gas_price']. Only ['data', 'from', 'gas', 'gasPrice', 'to', 'value'] are allowed",  # noqa: E501
                'id': 3,
                'jsonrpc': '2.0',
            }
        ),
        (
            # specifying nonce is invalid
            build_request('eth_estimateGas', params=[{
                'nonce': '0x01',
            }, 'latest']),
            {
                'error': "The following invalid fields were given in a transaction: ['nonce']. Only ['data', 'from', 'gas', 'gasPrice', 'to', 'value'] are allowed",  # noqa: E501
                'id': 3,
                'jsonrpc': '2.0',
            }
        ),
    ),
    ids=id_from_rpc_request,
)
async def test_estimate_gas_on_ipc(
        jsonrpc_ipc_pipe_path,
        request_msg,
        expected,
        event_loop,
        event_bus,
        ipc_server):
    result = await get_ipc_response(jsonrpc_ipc_pipe_path, request_msg, event_loop, event_bus)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'request_msg, expected',
    (
        (
            build_request('eth_call', params=[{'to': '0x' + '99' * 20}, 'latest']),
            {'result': '0x', 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('eth_call', params=[{
                'to': '0x' + '00' * 19 + '04',  # the 'identity' precompile
                'data': '0x123456',
            }, 'latest']),
            {'result': '0x123456', 'id': 3, 'jsonrpc': '2.0'},
        ),
    ),
    ids=id_from_rpc_request,
)
async def test_eth_call_on_ipc(
        jsonrpc_ipc_pipe_path,
        request_msg,
        expected,
        event_loop,
        event_bus,
        ipc_server):
    result = await get_ipc_response(jsonrpc_ipc_pipe_path, request_msg, event_loop, event_bus)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'signature, gas_price, expected',
    (
        (
            'getMeaningOfLife()',
            0,
            {
                'result': '0x000000000000000000000000000000000000000000000000000000000000002a',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
        (
            'getGasPrice()',
            0,
            {
                'result': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
        (
            'getGasPrice()',
            9,
            {
                'result': '0x0000000000000000000000000000000000000000000000000000000000000009',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
        (
            'doRevert()',
            0,
            {
                'error': 'Invalid opcode 0xfd @ 415',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
        (
            'useLotsOfGas()',
            0,
            {
                'error': 'Out of gas: Needed 700 - Remaining 444 - Reason: EXTCODESIZE',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
        (
            # make sure that whatever voodoo is used to execute a call, the balance is not inflated
            'getBalance()',
            1,
            {
                'result': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
    ),
)
async def test_eth_call_with_contract_on_ipc(
        chain,
        jsonrpc_ipc_pipe_path,
        simple_contract_address,
        signature,
        gas_price,
        event_loop,
        ipc_server,
        event_bus,
        expected):
    function_selector = function_signature_to_4byte_selector(signature)
    transaction = {
        'from': '0x' + 'ff' * 20,  # unfunded address
        'to': to_hex(simple_contract_address),
        'gasPrice': to_hex(gas_price),
        'data': to_hex(function_selector),
    }
    request_msg = build_request('eth_call', params=[transaction, 'latest'])
    result = await get_ipc_response(jsonrpc_ipc_pipe_path, request_msg, event_loop, event_bus)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'request_msg, event_bus_setup_fn, expected',
    (
        (
            build_request('net_peerCount'),
            mock_request_response(PeerCountRequest, PeerCountResponse(1)),
            {'result': '0x1', 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('net_peerCount'),
            mock_request_response(PeerCountRequest, PeerCountResponse(0)),
            {'result': '0x0', 'id': 3, 'jsonrpc': '2.0'},
        ),
    ),
    ids=[
        'net_peerCount_1', 'net_peerCount_0',
    ],
)
async def test_peer_pool_over_ipc(
        jsonrpc_ipc_pipe_path,
        request_msg,
        event_bus_setup_fn,
        event_bus,
        expected,
        event_loop,
        ipc_server):

    asyncio.ensure_future(event_bus_setup_fn(event_bus))

    result = await get_ipc_response(
        jsonrpc_ipc_pipe_path,
        request_msg,
        event_loop,
        event_bus,
    )
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'request_msg, event_bus_setup_fn, expected',
    (
        (
            build_request('eth_syncing'),
            mock_request_response(SyncingRequest, SyncingResponse(False, None)),
            {'result': False, 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('eth_syncing'),
            mock_request_response(SyncingRequest, SyncingResponse(True, SyncProgress(0, 1, 2))),
            {'result': {'startingBlock': 0, 'currentBlock': 1, 'highestBlock': 2}, 'id': 3,
             'jsonrpc': '2.0'},
        ),
    ),
    ids=[
        'eth_syncing_F', 'eth_syncing_T',
    ],
)
async def test_eth_over_ipc(
        jsonrpc_ipc_pipe_path,
        request_msg,
        event_bus_setup_fn,
        event_bus,
        expected,
        event_loop,
        ipc_server):

    asyncio.ensure_future(event_bus_setup_fn(event_bus))

    result = await get_ipc_response(
        jsonrpc_ipc_pipe_path,
        request_msg,
        event_loop,
        event_bus,
    )
    assert result == expected


GOOD_KEY = (
    '717ad99b1e67a93cd77806c9273d9195807da1db38ecfc535aa207598a4bd599'
    '645599a0d11f72c1107ba4fb44ab133b0188a2f0b47ff16ba12b0a5ec0350202'
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'request_msg, expected',
    (
        (
            build_request('admin_addPeer', ['enode://none@[::]:30303']),
            {
                'jsonrpc': '2.0',
                'id': 3, 'error':
                'public key must be a 128-character hex string'
            },
        ),
        (
            build_request('admin_addPeer', [f'enode://{GOOD_KEY}@[::]:30303']),
            {
                'jsonrpc': '2.0',
                'id': 3, 'error':
                'A concrete IP address must be specified'
            },
        ),
    ),
    ids=["Validation occurs", "Validation checks for ip address"],
)
async def test_admin_addPeer_error_messages(
        jsonrpc_ipc_pipe_path,
        request_msg,
        event_loop,
        event_bus,
        expected,
        ipc_server):

    result = await get_ipc_response(
        jsonrpc_ipc_pipe_path,
        request_msg,
        event_loop,
        event_bus,
    )
    assert result == expected


@pytest.mark.asyncio
async def test_admin_addPeer_fires_message(
        jsonrpc_ipc_pipe_path,
        event_loop,
        event_bus,
        ipc_server):

    future = asyncio.ensure_future(
        event_bus.wait_for(ConnectToNodeCommand), loop=event_loop
    )

    enode = f'enode://{GOOD_KEY}@10.0.0.1:30303'
    request = build_request('admin_addPeer', [enode])

    result = await get_ipc_response(
        jsonrpc_ipc_pipe_path,
        request,
        event_loop,
        event_bus
    )
    assert result == {'id': 3, 'jsonrpc': '2.0', 'result': None}

    event = await asyncio.wait_for(future, timeout=0.1, loop=event_loop)
    assert event.remote.uri() == enode


@pytest.fixture
def ipc_request(jsonrpc_ipc_pipe_path, event_loop, event_bus, ipc_server):
    async def make_request(*args):
        request = build_request(*args)
        return await get_ipc_response(
            jsonrpc_ipc_pipe_path, request, event_loop, event_bus
        )
    return make_request


@pytest.mark.asyncio
async def test_get_balance_works_for_block_number(
        chain_without_block_validation,
        ipc_request,
        funded_address,
        funded_address_initial_balance,
        funded_address_private_key
):
    block_no_before_transfer = (
        await ipc_request('eth_blockNumber', [])
    )['result']
    transfer_eth(
        chain=chain_without_block_validation,
        sender_private_key=funded_address_private_key,
        value=1,
        to=force_bytes_to_address(b'\x10\x10')
    )
    balance_before = (await ipc_request(
        'eth_getBalance',
        [funded_address.hex(), to_int(hexstr=block_no_before_transfer)]
    ))['result']
    assert balance_before == hex(funded_address_initial_balance)

    block_no_after_transfer = (
        await ipc_request('eth_blockNumber', [])
    )['result']
    balance_after = (await ipc_request(
        'eth_getBalance',
        [funded_address.hex(), to_int(hexstr=block_no_after_transfer)]
    ))['result']

    assert to_int(hexstr=balance_after) < to_int(hexstr=balance_before)
