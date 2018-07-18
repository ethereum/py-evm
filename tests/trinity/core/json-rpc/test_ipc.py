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


@pytest.fixture
def p2p_server(monkeypatch, p2p_server, mock_peer_pool):
    monkeypatch.setattr(p2p_server, 'peer_pool', mock_peer_pool)
    return p2p_server


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'request_msg, mock_peer_pool, expected',
    (
        (
            b'{}',
            MockPeerPool(),
            {'error': "Invalid Request: empty"},
        ),
        (
            build_request('notamethod'),
            MockPeerPool(),
            {'error': "Invalid RPC method: 'notamethod'", 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('eth_mining'),
            MockPeerPool(),
            {'result': False, 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('web3_clientVersion'),
            MockPeerPool(),
            {'result': construct_trinity_client_identifier(), 'id': 3, 'jsonrpc': '2.0'},
        ),
        (
            build_request('web3_sha3', ['0x89987239849872']),
            MockPeerPool(),
            {
                'result': '0xb3406131994d9c859de3c4400e12f630638e1e992c6453358c16d0e6ce2b1a70',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
        (
            build_request('web3_sha3', ['0x']),
            MockPeerPool(),
            {
                'result': '0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470',
                'id': 3,
                'jsonrpc': '2.0',
            },
        ),
        (
            build_request('net_version'),
            MockPeerPool(),
            {'result': '1337', 'id': 3, 'jsonrpc': '2.0'},
        ),
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
        (
            build_request('net_listening'),
            MockPeerPool(),
            {'result': True, 'id': 3, 'jsonrpc': '2.0'},
        ),
    ),
    ids=[
        'empty', 'notamethod', 'eth_mining', 'web3_clientVersion',
        'web3_sha3_1', 'web3_sha3_2', 'net_version', 'net_peerCount_1',
        'net_peerCount_0', 'net_listening_true',
    ],
)
async def test_ipc_requests(jsonrpc_ipc_pipe_path,
                            request_msg,
                            expected,
                            event_loop,
                            ipc_server):
    assert wait_for(jsonrpc_ipc_pipe_path), "IPC server did not successfully start with IPC file"

    reader, writer = await asyncio.open_unix_connection(str(jsonrpc_ipc_pipe_path), loop=event_loop)

    writer.write(request_msg)
    await writer.drain()
    result_bytes = await asyncio.tasks.wait_for(reader.readuntil(b'}'), 0.25, loop=event_loop)

    result = json.loads(result_bytes.decode())
    assert result == expected
    writer.close()
