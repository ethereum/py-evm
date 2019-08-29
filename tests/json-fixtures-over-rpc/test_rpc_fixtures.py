import asyncio
import json
import os
from pathlib import Path

import pytest

from eth_utils.toolz import (
    compose,
    dissoc,
    identity,
    get_in,
)

from eth_utils import (
    add_0x_prefix,
    is_address,
    is_hex,
    is_integer,
    is_string,
    to_checksum_address,
    to_tuple,
)
from eth_utils.curried import (
    apply_formatter_if,
)

from eth.chains.mainnet import (
    MainnetChain,
)
from eth.tools.fixtures import (
    filter_fixtures,
    generate_fixture_tests,
    load_fixture,
    should_run_slow_tests,
)

from trinity.chains.full import (
    FullChain,
)
from trinity.rpc import RPCServer
from trinity.rpc.format import (
    empty_to_0x,
    remove_leading_zeros,
)
from trinity.rpc.modules import (
    initialize_eth1_modules,
)


ROOT_PROJECT_DIR = Path(__file__).parent.parent.parent


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests')

SLOW_TESTS = (
    'Call1024PreCalls_d0g0v0',
    'ContractCreationSpam_d0g0v0_Homestead',
    'ContractCreationSpam_d0g0v0_Frontier',
    'Create2Recursive_d0g0v0',
    'Create2Recursive_d0g1v0',
    'ForkStressTest',
    'stQuadraticComplexityTest/Call50000_d0g1v0.json',
    'stQuadraticComplexityTest/QuadraticComplexitySolidity_CallDataCopy_d0g1v0.json',
    'stQuadraticComplexityTest/Return50000_2_d0g1v0.json',
    'stQuadraticComplexityTest/Return50000_d0g1v0.json',
    'stQuadraticComplexityTest/Callcode50000_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000_sha256_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000_ecrec_d0g1v0.json',
    'walletReorganizeOwners',
    'bcExploitTest/SuicideIssue.json',
    'static_Call1024PreCalls_d1g0v0',
    'static_Call1024PreCalls2_d0g0v0',
    'static_Call1024PreCalls2_d1g0v0',
    'static_Call1024PreCalls3_d1g0v0',
    'static_Call50000bytesContract50_1_d0g0v0',
    'static_Call50000_ecrec_d0g0v0',
    'static_Call50000_ecrec_d1g0v0',
    'static_Call50000_rip160_d0g0v0',
    'static_Call50000_rip160_d1g0v0',
    'static_Call50000_sha256_d0g0v0',
    'static_Call50000_sha256_d1g0v0',
    'static_Call50000_d0g0v0',
    'static_Call50000_d1g0v0',
    'static_Call50000_identity2_d0g0v0',
    'static_Call50000_identity2_d1g0v0',
    'static_Call50000_identity_d0g0v0',
    'static_Call50000_identity_d1g0v0',
    'static_Call50000bytesContract50_1_d1g0v0',
    'static_Call50000bytesContract50_2_d1g0v0',
    'static_LoopCallsThenRevert_d0g0v0',
    'static_LoopCallsThenRevert_d0g1v0',
    'static_Return50000_2_d0g0v0',
    'stQuadraticComplexityTest/Call50000_identity2_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000_identity_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000_rip160_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000bytesContract50_1_d0g1v0.json',
    'stQuadraticComplexityTest/Call50000bytesContract50_2_d0g1v0.json',
    'stQuadraticComplexityTest/Create1000_d0g1v0.json',
    'ShanghaiLove_Homestead',
    'ShanghaiLove_Frontier',
    'DelegateCallSpam',
)

# These are tests that are thought to be incorrect or buggy upstream,
# at the commit currently checked out in submodule `fixtures`.
# Ideally, this list should be empty.
# WHEN ADDING ENTRIES, ALWAYS PROVIDE AN EXPLANATION!
INCORRECT_UPSTREAM_TESTS = {
    # The test considers a "synthetic" scenario (the state described there can't
    # be arrived at using regular consensus rules).
    # * https://github.com/ethereum/py-evm/pull/1224#issuecomment-418775512
    # The result is in conflict with the yellow-paper:
    # * https://github.com/ethereum/py-evm/pull/1224#issuecomment-418800369
    ('GeneralStateTests/stRevertTest/RevertInCreateInInit_d0g0v0.json', 'RevertInCreateInInit_d0g0v0_Byzantium'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/RevertInCreateInInit_d0g0v0.json', 'RevertInCreateInInit_d0g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stRevertTest/RevertInCreateInInit_d0g0v0.json', 'RevertInCreateInInit_d0g0v0_ConstantinopleFix'),  # noqa: E501

    # The CREATE2 variant seems to have been derived from the one above - it, too,
    # has a "synthetic" state, on which py-evm flips.
    # * https://github.com/ethereum/py-evm/pull/1181#issuecomment-446330609
    ('GeneralStateTests/stCreate2/RevertInCreateInInitCreate2_d0g0v0.json', 'RevertInCreateInInitCreate2_d0g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stCreate2/RevertInCreateInInitCreate2_d0g0v0.json', 'RevertInCreateInInitCreate2_d0g0v0_ConstantinopleFix'),  # noqa: E501

    # Four variants have been specifically added to test a collision type
    # like the above; therefore, they fail in the same manner.
    # * https://github.com/ethereum/py-evm/pull/1579#issuecomment-446591118
    # Interestingly, d2 passes in Constantinople after a py-evm refactor of storage handling,
    # the same test is already passing in ConstantinopleFix. Since the situation is synthetic,
    # not much research went into why, yet.
    ('GeneralStateTests/stSStoreTest/InitCollision_d0g0v0.json', 'InitCollision_d0g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d1g0v0.json', 'InitCollision_d1g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d3g0v0.json', 'InitCollision_d3g0v0_Constantinople'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d0g0v0.json', 'InitCollision_d0g0v0_ConstantinopleFix'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d1g0v0.json', 'InitCollision_d1g0v0_ConstantinopleFix'),  # noqa: E501
    ('GeneralStateTests/stSStoreTest/InitCollision_d3g0v0.json', 'InitCollision_d3g0v0_ConstantinopleFix'),  # noqa: E501
}

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
    'gasLimit': 'gas',
}

RPC_TRANSACTION_NORMALIZERS = {
    'nonce': remove_leading_zeros,
    'gasLimit': remove_leading_zeros,
    'gasPrice': remove_leading_zeros,
    'value': remove_leading_zeros,
    'data': empty_to_0x,
    'to': compose(
        apply_formatter_if(is_address, to_checksum_address),
        add_0x_prefix
    ),
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


def blockchain_fixture_mark_fn(fixture_path, fixture_name, fixture_fork):
    for slow_test in SLOW_TESTS:
        if slow_test in fixture_path or slow_test in fixture_name:
            if not should_run_slow_tests():
                return pytest.mark.skip("skipping slow test on a quick run")
            break
    if (fixture_path, fixture_name) in INCORRECT_UPSTREAM_TESTS:
        return pytest.mark.xfail(reason="Listed in INCORRECT_UPSTREAM_TESTS.")


def generate_ignore_fn_for_fork(passed_fork):
    if passed_fork:
        normalized_fork = passed_fork.lower()

        def ignore_fn(fixture_path, fixture_key, fixture_fork):
            return fixture_fork.lower() != normalized_fork

        return ignore_fn


@to_tuple
def expand_fixtures_forks(all_fixtures):
    for fixture_path, fixture_key in all_fixtures:
        fixture = load_fixture(fixture_path, fixture_key)
        yield fixture_path, fixture_key, fixture['network']


def pytest_generate_tests(metafunc):
    ignore_fn = generate_ignore_fn_for_fork(metafunc.config.getoption('fork'))
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        preprocess_fn=expand_fixtures_forks,
        filter_fn=filter_fixtures(
            fixtures_base_dir=BASE_FIXTURE_PATH,
            mark_fn=blockchain_fixture_mark_fn,
            ignore_fn=ignore_fn
        ),
    )


def build_request(method, params):
    return {"jsonrpc": "2.0", "method": method, "params": params, "id": 3}


def result_from_response(response_str):
    response = json.loads(response_str)
    return (response.get('result', None), response.get('error', None))


async def call_rpc(rpc, method, params):
    request = build_request(method, params)
    response = await rpc.execute(request)
    return result_from_response(response)


async def assert_rpc_result(rpc, method, params, expected):
    result, error = await call_rpc(rpc, method, params)
    assert error is None
    assert result == expected
    return result


async def validate_account_attribute(*, fixture_key, rpc_method, rpc, state, addr, at_block):
    state_result, state_error = await call_rpc(rpc, rpc_method, [addr, at_block])
    assert state_result == state[fixture_key], "Invalid state - %s" % state_error


RPC_STATE_LOOKUPS = (
    ('balance', 'eth_getBalance'),
    ('code', 'eth_getCode'),
    ('nonce', 'eth_getTransactionCount'),
)


async def validate_account_state(rpc, state, addr, at_block):
    standardized_state = fixture_state_in_rpc_format(state)
    for fixture_key, rpc_method in RPC_STATE_LOOKUPS:
        await validate_account_attribute(
            fixture_key=fixture_key,
            rpc_method=rpc_method,
            rpc=rpc,
            state=standardized_state,
            addr=addr,
            at_block=at_block
        )
    for key in state['storage']:
        position = '0x0' if key == '0x' else key
        expected_storage = state['storage'][key]
        await assert_rpc_result(
            rpc,
            'eth_getStorageAt',
            [addr, position, at_block],
            expected_storage
        )


async def validate_accounts(rpc, states, at_block='latest'):
    for addr in states:
        await validate_account_state(rpc, states[addr], addr, at_block)


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


async def validate_transaction_count(rpc, block_fixture, at_block):
    if is_by_hash(at_block):
        rpc_method = 'eth_getBlockTransactionCountByHash'
    else:
        rpc_method = 'eth_getBlockTransactionCountByNumber'
    expected_transaction_count = hex(len(block_fixture['transactions']))
    await assert_rpc_result(rpc, rpc_method, [at_block], expected_transaction_count)


def validate_rpc_transaction_vs_fixture(transaction, fixture):
    expected = fixture_transaction_in_rpc_format(fixture)
    actual_transaction = dissoc(
        transaction,
        'hash',
        'from',
    )
    assert actual_transaction == expected


async def validate_transaction_by_index(rpc, transaction_fixture, at_block, index):
    if is_by_hash(at_block):
        rpc_method = 'eth_getTransactionByBlockHashAndIndex'
    else:
        rpc_method = 'eth_getTransactionByBlockNumberAndIndex'
    result, error = await call_rpc(rpc, rpc_method, [at_block, hex(index)])
    assert error is None
    validate_rpc_transaction_vs_fixture(result, transaction_fixture)


async def validate_block(rpc, block_fixture, at_block):
    if is_by_hash(at_block):
        rpc_method = 'eth_getBlockByHash'
    else:
        rpc_method = 'eth_getBlockByNumber'

    # validate without transaction bodies
    result, error = await call_rpc(rpc, rpc_method, [at_block, False])
    assert error is None
    validate_rpc_block_vs_fixture(result, block_fixture)
    assert len(result['transactions']) == len(block_fixture['transactions'])

    for index, transaction_fixture in enumerate(block_fixture['transactions']):
        await validate_transaction_by_index(rpc, transaction_fixture, at_block, index)

    await validate_transaction_count(rpc, block_fixture, at_block)

    # TODO validate transaction bodies
    result, error = await call_rpc(rpc, rpc_method, [at_block, True])
    # assert error is None
    # assert result['transactions'] == block_fixture['transactions']

    await validate_uncles(rpc, block_fixture, at_block)


async def validate_last_block(rpc, block_fixture):
    header = block_fixture['blockHeader']

    await validate_block(rpc, block_fixture, 'latest')
    await validate_block(rpc, block_fixture, header['hash'])
    await validate_block(rpc, block_fixture, int(header['number'], 16))


async def validate_uncle_count(rpc, block_fixture, at_block):
    if is_by_hash(at_block):
        rpc_method = 'eth_getUncleCountByBlockHash'
    else:
        rpc_method = 'eth_getUncleCountByBlockNumber'

    num_uncles = len(block_fixture['uncleHeaders'])
    await assert_rpc_result(rpc, rpc_method, [at_block], hex(num_uncles))


async def validate_uncle_headers(rpc, block_fixture, at_block):
    if is_by_hash(at_block):
        rpc_method = 'eth_getUncleByBlockHashAndIndex'
    else:
        rpc_method = 'eth_getUncleByBlockNumberAndIndex'

    for idx, uncle in enumerate(block_fixture['uncleHeaders']):
        result, error = await call_rpc(rpc, rpc_method, [at_block, hex(idx)])
        assert error is None
        validate_rpc_block_vs_fixture_header(result, uncle)


async def validate_uncles(rpc, block_fixture, at_block):
    await validate_uncle_count(rpc, block_fixture, at_block)
    await validate_uncle_headers(rpc, block_fixture, at_block)


@pytest.fixture
def chain_fixture(fixture_data):
    fixture_path, fixture_key, fixture_fork = fixture_data
    fixture = load_fixture(fixture_path, fixture_key)
    if fixture_fork == 'Istanbul':
        pytest.skip('Istanbul VM rules not yet supported')
    return fixture


class MainnetFullChain(FullChain):
    vm_configuration = MainnetChain.vm_configuration


@pytest.mark.asyncio
async def test_rpc_against_fixtures(event_bus, chain_fixture, fixture_data):
    chain = MainnetFullChain(None)
    rpc = RPCServer(initialize_eth1_modules(chain, event_bus), chain, event_bus)

    setup_result, setup_error = await call_rpc(rpc, 'evm_resetToGenesisFixture', [chain_fixture])
    # We need to advance the event loop for modules to be able to pickup the new chain
    await asyncio.sleep(0)
    assert setup_error is None and setup_result is True, "cannot load chain for {0}".format(fixture_data)  # noqa: E501

    await validate_accounts(rpc, chain_fixture['pre'])

    for block_fixture in chain_fixture['blocks']:
        should_be_good_block = 'blockHeader' in block_fixture

        if 'rlp_error' in block_fixture:
            assert not should_be_good_block
            continue

        block_result, block_error = await call_rpc(rpc, 'evm_applyBlockFixture', [block_fixture])

        if should_be_good_block:
            assert block_error is None
            assert block_result == block_fixture['rlp']

            await validate_block(rpc, block_fixture, block_fixture['blockHeader']['hash'])
        else:
            assert block_error is not None

    if chain_fixture.get('lastblockhash', None):
        for block_fixture in chain_fixture['blocks']:
            if get_in(['blockHeader', 'hash'], block_fixture) == chain_fixture['lastblockhash']:
                await validate_last_block(rpc, block_fixture)

    await validate_accounts(rpc, chain_fixture['postState'])
    await validate_accounts(rpc, chain_fixture['pre'], 'earliest')
    await validate_accounts(rpc, chain_fixture['pre'], 0)
