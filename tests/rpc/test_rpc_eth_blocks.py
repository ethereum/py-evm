import json
import os
import pytest

from eth_utils import (
    decode_hex,
)

from evm import MainnetTesterChain
from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.rpc import RPCServer


@pytest.fixture
def chain():
    server_test_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    db_path = os.path.join(server_test_path, 'fixtures', 'rpc_test_chain.db')
    db = MemoryDB()
    with open(db_path) as f:
        key_val_hex = json.loads(f.read())
        db.kv_store = {decode_hex(k): decode_hex(v) for k, v in key_val_hex.items()}
    chain_db = BaseChainDB(db)
    return MainnetTesterChain(chain_db)


@pytest.fixture
def rpc(chain):
    return RPCServer(chain)


def build_request(method, params):
    return {"jsonrpc": "2.0", "method": method, "params": params, "id": 3}


@pytest.mark.parametrize(
    'rpc_request, expected_result, expected_error',
    (
        (
            build_request(
                'eth_getBlockByHash',
                ["0xcfc6a6927c1097ebf66819044f63cdf28c541bb55ec555f8c6ca777db39d654d", False],
            ),
            {
                'hash': '0xcfc6a6927c1097ebf66819044f63cdf28c541bb55ec555f8c6ca777db39d654d',
                'difficulty': '0x20040',
                'extraData': '0x',
                'gasLimit': '0x2fefd8',
                'gasUsed': '0x0',
                'logsBloom': '0x' + '00' * 256,
                'miner': '0x7e5f4552091a69125d5dfcb7b8c2659029395bdf',
                'mixHash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'nonce': '0x0000000000000042',
                'number': '0x1',
                'parentHash': '0x41b0a7846ed8d068225b3ccf630812b4a03c6118bed310c1b0e4cdd2f16882e5',
                'receiptsRoot': '0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421',  # noqa: E501
                'sha3Uncles': '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347',
                'size': '0x1ff',
                'stateRoot': '0x5409c66ce1aa363c1af966dcccc69fb808f9da21d6e5c19c873f95864350521c',
                'timestamp': '0x5a2480df',
                'totalDifficulty': '0x40040',
                'transactions': [],
                'transactionsRoot': '0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421',  # noqa: E501
                'uncles': [],
            },
            None,
        ),
        (
            build_request('eth_notathing', []),
            None,
            "Method not implemented: 'eth_notathing'",
        ),
        (
            build_request('eth_accounts', []),
            None,
            "Method not implemented: 'eth_accounts'",
        ),
        (
            build_request('eth_blockNumber', []),
            "0x1",
            None,
        ),
        (
            build_request('eth_getBalance',
                ["0x7e5f4552091a69125d5dfcb7b8c2659029395bdf", 0],
            ),
            hex(1000000 * 10 ** 18),
            None,
        ),
        (
            build_request('eth_getBalance',
                ["0x7e5f4552091a69125d5dfcb7b8c2659029395bdf", "earliest"],
            ),
            hex(1000000 * 10 ** 18),
            None,
        ),
        (
            build_request('eth_getBalance',
                ["0x7e5f4552091a69125d5dfcb7b8c2659029395bdf", 1],
            ),
            hex(1000005 * 10 ** 18),
            None,
        ),
        (
            build_request('eth_getBalance',
                ["0x7e5f4552091a69125d5dfcb7b8c2659029395bdf", "latest"],
            ),
            hex(1000005 * 10 ** 18),
            None,
        ),
        # TODO issue a transaction in pending pool, so balance will test different from latest
        (
            build_request('eth_getBalance',
                ["0x7e5f4552091a69125d5dfcb7b8c2659029395bdf", "pending"],
            ),
            hex(1000005 * 10 ** 18),
            None,
        ),
    ),
)
def test_eth_requests(rpc, rpc_request, expected_result, expected_error):
    response_str = rpc.execute(rpc_request)
    response = json.loads(response_str)
    if expected_result:
        assert 'result' in response
        assert response['result'] == expected_result
    else:
        assert 'result' not in response

    if expected_error:
        assert response['error'] == expected_error
    else:
        assert 'error' not in response
