import asyncio
import json
import pytest


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
        (b'{}', None),
        (
            build_request('notamethod'),
            {'error': "Invalid RPC method: 'notamethod'", 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('eth_mining'),
            {'result': False, 'id': 3, 'jsonrpc': '2.0'},
        ),
    ),
)
async def test_ipc_requests(ipc_pipe, request_msg, expected):
    reader, writer = await asyncio.open_unix_connection(ipc_pipe)
    writer.write(request_msg)
    await writer.drain()
    try:
        result_bytes = await asyncio.tasks.wait_for(reader.readuntil(b'}'), 0.25)
        result = json.loads(result_bytes.decode())
    except asyncio.TimeoutError:
        result = None
    assert result == expected
