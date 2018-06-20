import json
import os
import pytest

from cytoolz import (
    dissoc,
    identity,
    get_in,
)

from eth_utils import (
    add_0x_prefix,
    is_hex,
    is_integer,
    is_string,
)

from evm.tools.fixture_tests import (
    filter_fixtures,
    generate_fixture_tests,
    load_fixture,
    should_run_slow_tests,
)

from trinity.rpc import RPCServer
from trinity.rpc.format import (
    empty_to_0x,
    remove_leading_zeros,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests')

SLOW_TESTS = (
    'Call1024PreCalls_d0g0v0_Byzantium',
    'Call1024PreCalls_d0g0v0_EIP150',
    'Call1024PreCalls_d0g0v0_EIP158',
    'ContractCreationSpam_d0g0v0_Homestead',
    'ContractCreationSpam_d0g0v0_Frontier',
    'ForkStressTest_EIP150',
    'ForkStressTest_EIP158',
    'ForkStressTest_Homestead',
    'ForkStressTest_Frontier',
    'ForkStressTest_Byzantium',
    'stQuadraticComplexityTest/Call50000_d0g1v0.json',
    'stQuadraticComplexityTest/QuadraticComplexitySolidity_CallDataCopy_d0g1v0.json',
    'stQuadraticComplexityTest/Return50000_2_d0g1v0.json',
    'stQuadraticComplexityTest/Return50000_d0g1v0.json',
    'stQuadraticComplexityTest/Callcode50000_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000_sha256_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000_ecrec_d0g1v0.json',
    'walletReorganizeOwners',
    'bcExploitTest/SuicideIssue.json',
    'DelegateCallSpam_Homestead',
    'static_Call50000_sha256_d0g0v0_Byzantium',
    'static_Call50000_rip160_d0g0v0_Byzantium',
    'static_Call50000_rip160_d1g0v0_Byzantium',
    'static_Call50000_sha256_d1g0v0_Byzantium',
    'static_Call50000_ecrec_d1g0v0_Byzantium',
    'static_Call50000_d1g0v0_Byzantium',
    'static_Call50000_d0g0v0_Byzantium',
    'static_Call50000_ecrec_d0g0v0_Byzantium',
    'static_Call50000_identity2_d0g0v0_Byzantium',
    'static_Call50000_identity_d1g0v0_Byzantium',
    'static_Call50000_identity_d0g0v0_Byzantium',
    'static_Call50000bytesContract50_1_d1g0v0_Byzantium',
    'static_Call50000bytesContract50_2_d1g0v0_Byzantium',
    'static_LoopCallsThenRevert_d0g0v0_Byzantium',
    'static_LoopCallsThenRevert_d0g1v0_Byzantium',
    'Call1024PreCalls_d0g0v0_Byzantium',
    'Call1024PreCalls_d0g0v0_EIP158',
    'Call1024PreCalls_d0g0v0_EIP150',
    'Call1024PreCalls_d0g0v0_Byzantium',
    'Call1024PreCalls_d0g0v0_EIP150',
    'Call1024PreCalls_d0g0v0_EIP158',
    'stQuadraticComplexityTest/Call50000_identity2_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000_identity_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000_rip160_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000bytesContract50_1_d0g1v0.json',
    'stQuadraticComplexityTest/Create1000_d0g1v0.json',
    'ShanghaiLove_Homestead',
    'ShanghaiLove_Frontier',
    'DelegateCallSpam_EIP158',
    'DelegateCallSpam_Byzantium',
    'DelegateCallSpam_EIP150',
)

RPC_STATE_NORMALIZERS = {
    'balance': remove_leading_zeros,
    'code': empty_to_0x,
    'nonce': remove_leading_zeros,
}

RPC_BLOCK_REMAPPERS = {
    'bloom': 'logsBloom',
    'coinbase': 'miner',
    'transactionsTrie': 'transactionsRoot',
    'uncleHash': 'sha3Uncles',
    'receiptTrie': 'receiptsRoot',
}

RPC_BLOCK_NORMALIZERS = {
    'difficulty': remove_leading_zeros,
    'extraData': empty_to_0x,
    'gasLimit': remove_leading_zeros,
    'gasUsed': remove_leading_zeros,
    'number': remove_leading_zeros,
    'timestamp': remove_leading_zeros,
}

RPC_TRANSACTION_REMAPPERS = {
    'data': 'input',
}

RPC_TRANSACTION_NORMALIZERS = {
    'nonce': remove_leading_zeros,
    'gasLimit': remove_leading_zeros,
    'gasPrice': remove_leading_zeros,
    'value': remove_leading_zeros,
    'data': empty_to_0x,
    'to': add_0x_prefix,
    'r': remove_leading_zeros,
    's': remove_leading_zeros,
    'v': remove_leading_zeros,
}


def fixture_block_in_rpc_format(state):
    return {
        RPC_BLOCK_REMAPPERS.get(key, key):
        RPC_BLOCK_NORMALIZERS.get(key, identity)(value)
        for key, value in state.items()
    }


def fixture_state_in_rpc_format(state):
    return {
        key: RPC_STATE_NORMALIZERS.get(key, identity)(value)
        for key, value in state.items()
    }


def fixture_transaction_in_rpc_format(state):
    return {
        RPC_TRANSACTION_REMAPPERS.get(key, key):
        RPC_TRANSACTION_NORMALIZERS.get(key, identity)(value)
        for key, value in state.items()
    }


def blockchain_fixture_mark_fn(fixture_path, fixture_name):
    for slow_test in SLOW_TESTS:
        if slow_test in fixture_path or slow_test in fixture_name:
            if not should_run_slow_tests():
                return pytest.mark.skip("skipping slow test on a quick run")
            break


def pytest_generate_tests(metafunc):
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        filter_fn=filter_fixtures(
            fixtures_base_dir=BASE_FIXTURE_PATH,
            mark_fn=blockchain_fixture_mark_fn,
        ),
    )


def build_request(method, params):
    return {"jsonrpc": "2.0", "method": method, "params": params, "id": 3}


def result_from_response(response_str):
    response = json.loads(response_str)
    return (response.get('result', None), response.get('error', None))


def call_rpc(rpc, method, params):
    request = build_request(method, params)
    response = rpc.execute(request)
    return result_from_response(response)


def assert_rpc_result(rpc, method, params, expected):
    result, error = call_rpc(rpc, method, params)
    assert error is None
    assert result == expected
    return result


def validate_account_attribute(fixture_key, rpc_method, rpc, state, addr, at_block):
    state_result, state_error = call_rpc(rpc, rpc_method, [addr, at_block])
    assert state_result == state[fixture_key], "Invalid state - %s" % state_error


RPC_STATE_LOOKUPS = (
    ('balance', 'eth_getBalance'),
    ('code', 'eth_getCode'),
    ('nonce', 'eth_getTransactionCount'),
)


def validate_account_state(rpc, state, addr, at_block):
    standardized_state = fixture_state_in_rpc_format(state)
    for fixture_key, rpc_method in RPC_STATE_LOOKUPS:
        validate_account_attribute(fixture_key, rpc_method, rpc, standardized_state, addr, at_block)
    for key in state['storage']:
        position = '0x0' if key == '0x' else key
        expected_storage = state['storage'][key]
        assert_rpc_result(rpc, 'eth_getStorageAt', [addr, position, at_block], expected_storage)


def validate_accounts(rpc, states, at_block='latest'):
    for addr in states:
        validate_account_state(rpc, states[addr], addr, at_block)


def validate_rpc_block_vs_fixture(block, block_fixture):
    return validate_rpc_block_vs_fixture_header(block, block_fixture['blockHeader'])


def validate_rpc_block_vs_fixture_header(block, header_fixture):
    expected = fixture_block_in_rpc_format(header_fixture)
    actual_block = dissoc(
        block,
        'size',
        'totalDifficulty',
        'transactions',
        'uncles',
    )
    assert actual_block == expected


def is_by_hash(at_block):
    if is_string(at_block) and is_hex(at_block) and len(at_block) == 66:
        return True
    elif is_integer(at_block) or at_block in ('latest', 'earliest', 'pending'):
        return False
    else:
        raise ValueError("Unrecognized 'at_block' value: %r" % at_block)


def validate_transaction_count(rpc, block_fixture, at_block):
    if is_by_hash(at_block):
        rpc_method = 'eth_getBlockTransactionCountByHash'
    else:
        rpc_method = 'eth_getBlockTransactionCountByNumber'
    expected_transaction_count = hex(len(block_fixture['transactions']))
    assert_rpc_result(rpc, rpc_method, [at_block], expected_transaction_count)


def validate_rpc_transaction_vs_fixture(transaction, fixture):
    expected = fixture_transaction_in_rpc_format(fixture)
    actual_transaction = dissoc(
        transaction,
        'hash',
    )
    assert actual_transaction == expected


def validate_transaction_by_index(rpc, transaction_fixture, at_block, index):
    if is_by_hash(at_block):
        rpc_method = 'eth_getTransactionByBlockHashAndIndex'
    else:
        rpc_method = 'eth_getTransactionByBlockNumberAndIndex'
    result, error = call_rpc(rpc, rpc_method, [at_block, hex(index)])
    assert error is None
    validate_rpc_transaction_vs_fixture(result, transaction_fixture)


def validate_block(rpc, block_fixture, at_block):
    if is_by_hash(at_block):
        rpc_method = 'eth_getBlockByHash'
    else:
        rpc_method = 'eth_getBlockByNumber'

    # validate without transaction bodies
    result, error = call_rpc(rpc, rpc_method, [at_block, False])
    assert error is None
    validate_rpc_block_vs_fixture(result, block_fixture)
    assert len(result['transactions']) == len(block_fixture['transactions'])

    for index, transaction_fixture in enumerate(block_fixture['transactions']):
        validate_transaction_by_index(rpc, transaction_fixture, at_block, index)

    validate_transaction_count(rpc, block_fixture, at_block)

    # TODO validate transaction bodies
    result, error = call_rpc(rpc, rpc_method, [at_block, True])
    # assert error is None
    # assert result['transactions'] == block_fixture['transactions']

    validate_uncles(rpc, block_fixture, at_block)


def validate_last_block(rpc, block_fixture):
    header = block_fixture['blockHeader']

    validate_block(rpc, block_fixture, 'latest')
    validate_block(rpc, block_fixture, header['hash'])
    validate_block(rpc, block_fixture, int(header['number'], 16))


def validate_uncle_count(rpc, block_fixture, at_block):
    if is_by_hash(at_block):
        rpc_method = 'eth_getUncleCountByBlockHash'
    else:
        rpc_method = 'eth_getUncleCountByBlockNumber'

    num_uncles = len(block_fixture['uncleHeaders'])
    assert_rpc_result(rpc, rpc_method, [at_block], hex(num_uncles))


def validate_uncle_headers(rpc, block_fixture, at_block):
    if is_by_hash(at_block):
        rpc_method = 'eth_getUncleByBlockHashAndIndex'
    else:
        rpc_method = 'eth_getUncleByBlockNumberAndIndex'

    for idx, uncle in enumerate(block_fixture['uncleHeaders']):
        result, error = call_rpc(rpc, rpc_method, [at_block, hex(idx)])
        assert error is None
        validate_rpc_block_vs_fixture_header(result, uncle)


def validate_uncles(rpc, block_fixture, at_block):
    validate_uncle_count(rpc, block_fixture, at_block)
    validate_uncle_headers(rpc, block_fixture, at_block)


@pytest.fixture
def chain_fixture(fixture_data):
    fixture = load_fixture(*fixture_data)
    if fixture['network'] == 'Constantinople':
        pytest.skip('Constantinople VM rules not yet supported')
    return fixture


def test_rpc_against_fixtures(ipc_server, chain_fixture, fixture_data):
    rpc = RPCServer(None)

    setup_result, setup_error = call_rpc(rpc, 'evm_resetToGenesisFixture', [chain_fixture])
    assert setup_error is None and setup_result is True, "cannot load chain for %r" % fixture_data

    validate_accounts(rpc, chain_fixture['pre'])

    for block_fixture in chain_fixture['blocks']:
        should_be_good_block = 'blockHeader' in block_fixture

        if 'rlp_error' in block_fixture:
            assert not should_be_good_block
            continue

        block_result, block_error = call_rpc(rpc, 'evm_applyBlockFixture', [block_fixture])

        if should_be_good_block:
            assert block_error is None
            assert block_result == block_fixture['rlp']

            validate_block(rpc, block_fixture, block_fixture['blockHeader']['hash'])
        else:
            assert block_error is not None

    if chain_fixture.get('lastblockhash', None):
        for block_fixture in chain_fixture['blocks']:
            if get_in(['blockHeader', 'hash'], block_fixture) == chain_fixture['lastblockhash']:
                validate_last_block(rpc, block_fixture)

    validate_accounts(rpc, chain_fixture['postState'])
    validate_accounts(rpc, chain_fixture['pre'], 'earliest')
    validate_accounts(rpc, chain_fixture['pre'], 0)
