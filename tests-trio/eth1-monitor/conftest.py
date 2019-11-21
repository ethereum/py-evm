import functools
import json
import tempfile
from pathlib import Path
import uuid


import pytest
import trio
import ssz
import eth_utils

from eth_tester import EthereumTester, PyEVMBackend

from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider
from lahja.trio.endpoint import TrioEndpoint
from lahja import ConnectionConfig

from p2p.trio_service import background_service
from trinity.components.eth2.eth1_monitor.configs import deposit_contract_json
from trinity.components.eth2.eth1_monitor.eth1_monitor import Eth1Monitor
from trinity.components.eth2.eth1_monitor.factories import DepositDataFactory
from trinity.tools.factories.db import AtomicDBFactory


# Ref: https://github.com/ethereum/eth2.0-specs/blob/dev/deposit_contract/tests/contracts/conftest.py  # noqa: E501


@pytest.fixture("session")
def contract_json():
    return json.loads(deposit_contract_json)


@pytest.fixture
def tester():
    return EthereumTester(PyEVMBackend())


@pytest.fixture
def a0(tester):
    return tester.get_accounts()[0]


@pytest.fixture
def w3(tester):
    web3 = Web3(EthereumTesterProvider(tester))
    return web3


@pytest.fixture
def num_blocks_confirmed():
    return 3


@pytest.fixture
def polling_period():
    return 0.01


@pytest.fixture
def start_block_number():
    return 1


@pytest.fixture
def deposit_contract(w3, tester, contract_json):
    contract_bytecode = contract_json["bytecode"]
    contract_abi = contract_json["abi"]
    registration = w3.eth.contract(abi=contract_abi, bytecode=contract_bytecode)
    tx_hash = registration.constructor().transact()
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
    assert tx_receipt["status"]
    registration_deployed = w3.eth.contract(
        address=tx_receipt.contractAddress, abi=contract_abi
    )
    return registration_deployed


@pytest.fixture
def func_do_deposit(w3, deposit_contract):
    return functools.partial(deposit, w3=w3, deposit_contract=deposit_contract)


@pytest.fixture
async def eth1_monitor(
    w3,
    deposit_contract,
    num_blocks_confirmed,
    polling_period,
    endpoint_server,
    start_block_number,
):
    m = Eth1Monitor(
        w3=w3,
        deposit_contract_address=deposit_contract.address,
        deposit_contract_abi=deposit_contract.abi,
        num_blocks_confirmed=num_blocks_confirmed,
        polling_period=polling_period,
        start_block_number=start_block_number,
        event_bus=endpoint_server,
        base_db=AtomicDBFactory(),
    )
    async with background_service(m):
        yield m


def deposit(w3, deposit_contract) -> int:
    deposit_data = DepositDataFactory()
    deposit_input = (
        deposit_data.pubkey,
        deposit_data.withdrawal_credentials,
        deposit_data.signature,
        ssz.get_hash_tree_root(deposit_data),
    )
    tx_hash = deposit_contract.functions.deposit(*deposit_input).transact(
        {"value": deposit_data.amount * eth_utils.denoms.gwei}
    )
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
    assert tx_receipt["status"]
    return deposit_data.amount


# Fixtures below are copied from https://github.com/ethereum/lahja/blob/f0b7ead13298de82c02ed92cfb2d32a8bc00b42a/tests/core/trio/conftest.py  # noqa: E501


@pytest.fixture
def ipc_base_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def generate_unique_name() -> str:
    # We use unique names to avoid clashing of IPC pipes
    return str(uuid.uuid4())


@pytest.fixture
def endpoint_server_config(ipc_base_path):
    config = ConnectionConfig.from_name(generate_unique_name(), base_path=ipc_base_path)
    return config


@pytest.fixture
async def endpoint_server(endpoint_server_config):
    async with TrioEndpoint.serve(endpoint_server_config) as endpoint:
        yield endpoint


@pytest.fixture
async def endpoint_client(endpoint_server_config, endpoint_server):
    async with TrioEndpoint("client-for-testing").run() as client:
        await client.connect_to_endpoints(endpoint_server_config)
        while not endpoint_server.is_connected_to("client-for-testing"):
            await trio.sleep(0)
        yield client
