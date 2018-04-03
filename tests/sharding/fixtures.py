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
from evm.vm.forks.sharding.vmc_handler import (
    VMCHandler,
)
from evm.vm.forks.sharding.vmc_utils import (
    get_vmc_json,
)
from tests.sharding.web3_utils import (
    get_code,
    get_nonce,
    send_raw_transaction,
    mine,
)


def make_deploy_vmc_tx(TransactionClass, gas_price):
    vmc_json = get_vmc_json()
    vmc_bytecode = decode_hex(vmc_json['bytecode'])
    v = 27
    r = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    s = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    return TransactionClass(0, gas_price, 3000000, b'', 0, vmc_bytecode, v, r, s)


def get_contract_address_from_deploy_tx(transaction):
    return pipe(
        transaction.sender,
        to_canonical_address,
        functools.partial(generate_contract_address, nonce=0),
    )


def deploy_vmc_contract(web3, gas_price, privkey):
    deploy_vmc_tx = make_deploy_vmc_tx(ByzantiumTransaction, gas_price=gas_price)

    # fund the vmc contract deployer
    fund_deployer_tx = ByzantiumTransaction.create_unsigned_transaction(
        get_nonce(web3, privkey.public_key.to_canonical_address()),
        gas_price,
        500000,
        deploy_vmc_tx.sender,
        deploy_vmc_tx.gas * deploy_vmc_tx.gas_price + deploy_vmc_tx.value,
        b'',
    ).as_signed_transaction(privkey)
    fund_deployer_tx_hash = send_raw_transaction(web3, fund_deployer_tx)
    mine(web3, 1)
    assert web3.eth.getTransactionReceipt(fund_deployer_tx_hash) is not None

    # deploy vmc contract
    deploy_vmc_tx_hash = send_raw_transaction(web3, deploy_vmc_tx)
    mine(web3, 1)
    assert web3.eth.getTransactionReceipt(deploy_vmc_tx_hash) is not None

    return get_contract_address_from_deploy_tx(deploy_vmc_tx)


@pytest.fixture
def vmc_handler():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    if hasattr(w3.eth, "enable_unaudited_features"):
        w3.eth.enable_unaudited_features()

    default_privkey = get_default_account_keys()[0]
    # deploy vmc contract
    vmc_addr = deploy_vmc_contract(
        w3,
        get_sharding_config()['GAS_PRICE'],
        default_privkey,
    )
    assert get_code(w3, vmc_addr) != b''

    # setup vmc_handler's web3.eth.contract instance
    vmc_json = get_vmc_json()
    vmc_abi = vmc_json['abi']
    vmc_bytecode = vmc_json['bytecode']
    VMCHandlerClass = VMCHandler.factory(w3, abi=vmc_abi, bytecode=vmc_bytecode)
    vmc_handler = VMCHandlerClass(
        to_checksum_address(vmc_addr),
        default_privkey=default_privkey,
    )

    return vmc_handler
