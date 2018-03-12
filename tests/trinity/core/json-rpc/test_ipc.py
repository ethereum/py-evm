import asyncio
import json
import os
import pytest
import time


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
    ),
    ids=['empty', 'notamethod', 'eth_mining'],
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
