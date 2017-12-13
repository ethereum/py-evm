import json
import os
import pytest

from evm.rpc import RPCServer
from evm.rpc.format import (
    fixture_state_in_rpc_format,
)

from evm.utils.fixture_tests import (
    filter_fixtures,
    generate_fixture_tests,
    load_fixture,
)

ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests', 'bcValidBlockTest')


def blockchain_fixture_mark_fn(fixture_path, fixture_name):
    if fixture_path.startswith('bcExploitTest'):
        return pytest.mark.skip("Exploit tests are slow")
    elif fixture_path == 'bcWalletTest/walletReorganizeOwners.json':
        return pytest.mark.skip("Wallet owner reorganizatio tests are slow")


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
        storage_result, storage_error = call_rpc(rpc, 'eth_getStorageAt', [addr, key, at_block])
        assert storage_error is None
        assert storage_result == state['storage'][key]


def validate_accounts(rpc, states, at_block='latest'):
    for addr in states:
        validate_account_state(rpc, states[addr], addr, at_block)


@pytest.fixture
def chain_fixture(fixture_data):
    fixture = load_fixture(*fixture_data)
    if fixture['network'] == 'Constantinople':
        pytest.skip('Constantinople VM rules not yet supported')
    return fixture


def test_rpc_against_fixtures(chain_fixture, fixture_data):
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
        else:
            assert block_error is not None

    validate_accounts(rpc, chain_fixture['postState'])
    validate_accounts(rpc, chain_fixture['pre'], 'earliest')
    validate_accounts(rpc, chain_fixture['pre'], 0)
