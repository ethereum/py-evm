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
    ),
    ids=[
        'empty', 'notamethod', 'eth_mining', 'web3_clientVersion',
        'web3_sha3_1', 'web3_sha3_2', 'net_version',
    ],
)
async def test_ipc_requests(jsonrpc_ipc_pipe_path,
                            request_msg,
                            expected,
                            event_loop,
                            ipc_server):
    assert wait_for(jsonrpc_ipc_pipe_path), "IPC server did not successfully start with IPC file"

    reader, writer = await asyncio.open_unix_connection(jsonrpc_ipc_pipe_path, loop=event_loop)

    writer.write(request_msg)
    await writer.drain()
    result_bytes = await asyncio.tasks.wait_for(reader.readuntil(b'}'), 0.25, loop=event_loop)

    result = json.loads(result_bytes.decode())
    assert result == expected
    writer.close()
