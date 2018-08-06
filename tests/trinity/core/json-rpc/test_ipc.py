import asyncio
import json
import os
import pytest
import time


from trinity.utils.version import construct_trinity_client_identifier


def wait_for(path):
    for _ in range(100):
        if os.path.exists(path):
            return True
        time.sleep(0.01)
    return False


def build_request(method, params=[]):
    request = {
        'jsonrpc': '2.0',
        'id': 3,
        'method': method,
        'params': params,
    }
    return json.dumps(request).encode()


class MockPeerPool:

    def __init__(self, peer_count=0):
        self.peer_count = peer_count

    def __len__(self):
        return self.peer_count


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
        event_loop):
    assert wait_for(jsonrpc_ipc_pipe_path), "IPC server did not successfully start with IPC file"

    reader, writer = await asyncio.open_unix_connection(str(jsonrpc_ipc_pipe_path), loop=event_loop)

    writer.write(request_msg)
    await writer.drain()
    result_bytes = b''
    while not can_decode_json(result_bytes):
        result_bytes += await asyncio.tasks.wait_for(reader.readuntil(b'}'), 0.25, loop=event_loop)

    writer.close()
    return json.loads(result_bytes.decode())


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
            build_request('net_version'),
            {'result': '1337', 'id': 3, 'jsonrpc': '2.0'},
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
        ipc_server):
    result = await get_ipc_response(jsonrpc_ipc_pipe_path, request_msg, event_loop)
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
            {'result': hex(65483), 'id': 3, 'jsonrpc': '2.0'},
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
        ipc_server):
    result = await get_ipc_response(jsonrpc_ipc_pipe_path, request_msg, event_loop)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'request_msg, mock_peer_pool, expected',
    (
        (
            build_request('net_peerCount'),
            MockPeerPool(peer_count=1),
            {'result': '0x1', 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('net_peerCount'),
            MockPeerPool(peer_count=0),
            {'result': '0x0', 'id': 3, 'jsonrpc': '2.0'},
        ),
    ),
    ids=[
        'net_peerCount_1', 'net_peerCount_0',
    ],
)
async def test_peer_pool_over_ipc(
        monkeypatch,
        jsonrpc_ipc_pipe_path,
        request_msg,
        mock_peer_pool,
        expected,
        event_loop,
        ipc_server):
    monkeypatch.setattr(ipc_server.rpc.modules['net'], '_peer_pool', mock_peer_pool)
    result = await get_ipc_response(jsonrpc_ipc_pipe_path, request_msg, event_loop)
    assert result == expected
