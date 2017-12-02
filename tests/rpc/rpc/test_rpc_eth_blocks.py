import json
import os
import pytest

from evm import MainnetTesterChain
from evm.db.backends.level import LevelDB
from evm.db.chain import BaseChainDB
from evm.rpc import RPCServer


@pytest.fixture
def chain():
    server_test_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    db_path = os.path.join(server_test_path, 'mainnet_tester_chain.db')
    db = BaseChainDB(LevelDB(db_path))
    return MainnetTesterChain(db)


@pytest.fixture
def rpc(chain):
    return RPCServer(chain)


def build_request(method, args):
    return '{"jsonrpc":"2.0","method":"%s","params":%s,"id":3}' % (
        method,
        json.dumps(args),
    )


@pytest.mark.parametrize(
    'rpc_request, expected_result, expected_error',
    (
        (
            build_request(
                'eth_getBlockByHash',
                ["0xdc5a98984e704c854e9f0355d9c70518b842fc0ac6d9665b2f3010c6ec623cb5", False],
            ),
            {
                'hash': '0xdc5a98984e704c854e9f0355d9c70518b842fc0ac6d9665b2f3010c6ec623cb5',
                'difficulty': '0x20040',
                'extraData': '0x',
                'gasLimit': '0x2fefd8',
                'gasUsed': '0x0',
                'logsBloom': '0x' + '00' * 256,
                'miner': '0x7e5f4552091a69125d5dfcb7b8c2659029395bdf',
                'mixHash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'nonce': '0x0000000000000042',
                'number': '0x1',
                'parentHash': '0x34ec7f92fe74fd769efaf7155ca427b23aa0d5e7850b019a1e08d956fd295a21',
                'receiptsRoot': '0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421',  # noqa: E501
                'sha3Uncles': '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347',
                'size': '0x1ff',
                'stateRoot': '0x5409c66ce1aa363c1af966dcccc69fb808f9da21d6e5c19c873f95864350521c',
                'timestamp': '0x5a21f707',
                'totalDifficulty': '0x40040',
                'transactions': [],
                'transactionsRoot': '0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421',  # noqa: E501
                'uncles': [],
            },
            None,
        ),
    ),
)
def test_eth_requests(rpc, rpc_request, expected_result, expected_error):
    response_str = rpc.request(rpc_request)
    response = json.loads(response_str)
    if expected_result:
        assert 'result' in response
        assert response['result'] == expected_result
    else:
        assert 'result' not in response

    if expected_error:
        response['error'] == expected_error
    else:
        assert 'error' not in response
