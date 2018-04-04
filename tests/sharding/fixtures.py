import functools
import pytest

from cytoolz import (
    pipe,
)

from web3 import (
    Web3,
)

from web3.providers.eth_tester import (
    EthereumTesterProvider,
)

from eth_utils import (
    to_canonical_address,
    to_checksum_address,
    decode_hex,
)

from eth_tester import (
    EthereumTester,
)

from eth_tester.backends.pyevm import (
    PyEVMBackend,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from evm.vm.forks.byzantium.transactions import (
    ByzantiumTransaction,
)

from evm.utils.address import (
    generate_contract_address,
)

from evm.vm.forks.sharding.config import (
    get_sharding_config,
)
from evm.vm.forks.sharding.smc_handler import (
    SMCHandler,
)
from evm.vm.forks.sharding.smc_utils import (
    get_smc_json,
)
from tests.sharding.web3_utils import (
    get_code,
    get_nonce,
    send_raw_transaction,
    mine,
)


def make_deploy_smc_tx(TransactionClass, gas_price):
    smc_json = get_smc_json()
    smc_bytecode = decode_hex(smc_json['bytecode'])
    v = 27
    r = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    s = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    return TransactionClass(0, gas_price, 3000000, b'', 0, smc_bytecode, v, r, s)


def get_contract_address_from_deploy_tx(transaction):
    return pipe(
        transaction.sender,
        to_canonical_address,
        functools.partial(generate_contract_address, nonce=0),
    )


def deploy_smc_contract(web3, gas_price, privkey):
    deploy_smc_tx = make_deploy_smc_tx(ByzantiumTransaction, gas_price=gas_price)

    # fund the smc contract deployer
    fund_deployer_tx = ByzantiumTransaction.create_unsigned_transaction(
        get_nonce(web3, privkey.public_key.to_canonical_address()),
        gas_price,
        500000,
        deploy_smc_tx.sender,
        deploy_smc_tx.gas * deploy_smc_tx.gas_price + deploy_smc_tx.value,
        b'',
    ).as_signed_transaction(privkey)
    fund_deployer_tx_hash = send_raw_transaction(web3, fund_deployer_tx)
    mine(web3, 1)
    assert web3.eth.getTransactionReceipt(fund_deployer_tx_hash) is not None

    # deploy smc contract
    deploy_smc_tx_hash = send_raw_transaction(web3, deploy_smc_tx)
    mine(web3, 1)
    assert web3.eth.getTransactionReceipt(deploy_smc_tx_hash) is not None

    return get_contract_address_from_deploy_tx(deploy_smc_tx)


@pytest.fixture
def smc_handler():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    if hasattr(w3.eth, "enable_unaudited_features"):
        w3.eth.enable_unaudited_features()

    default_privkey = get_default_account_keys()[0]
    # deploy smc contract
    smc_addr = deploy_smc_contract(
        w3,
        get_sharding_config()['GAS_PRICE'],
        default_privkey,
    )
    assert get_code(w3, smc_addr) != b''

    # setup smc_handler's web3.eth.contract instance
    smc_json = get_smc_json()
    smc_abi = smc_json['abi']
    smc_bytecode = smc_json['bytecode']
    SMCHandlerClass = SMCHandler.factory(w3, abi=smc_abi, bytecode=smc_bytecode)
    smc_handler = SMCHandlerClass(
        to_checksum_address(smc_addr),
        default_privkey=default_privkey,
    )

    return smc_handler
