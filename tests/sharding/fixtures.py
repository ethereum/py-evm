import functools
import pytest

from cytoolz import (
    pipe,
)

from web3 import (
    Web3,
    HTTPProvider,
)

from web3.providers.eth_tester import (
    EthereumTesterProvider,
)

<<<<<<< HEAD
from eth_tester import (
    EthereumTester,
)
=======
from eth_utils import (
    to_checksum_address,
)

from eth_tester import EthereumTester
>>>>>>> Add `get_next_log` and `fetch_candidate_head`

from eth_tester.backends.pyevm import (
    PyEVMBackend,
)

<<<<<<< HEAD
from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
=======
from evm.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
)

from evm.chains.sharding.mainchain_handler.mainchain_handler import (
    MainchainHandler,
>>>>>>> Add `get_next_log` and `fetch_candidate_head`
)
from evm.chains.sharding.mainchain_handler.vmc_handler import (
    VMC,
)
from evm.chains.sharding.mainchain_handler.vmc_utils import (
    create_vmc_tx,
    get_contract_address_from_contract_tx,
    get_vmc_json,
)

from eth_utils import (
    to_canonical_address,
    to_checksum_address,
)

from evm.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
)

from evm.utils.address import (
    generate_contract_address,
)

from evm.vm.forks.sharding.config import (
    get_sharding_config,
)
from evm.vm.forks.sharding.vmc_handler import (
    VMC,
)
from evm.vm.forks.sharding.vmc_utils import (
    create_vmc_tx,
    get_vmc_json,
)


def get_contract_address_from_contract_tx(transaction):
    return pipe(
        transaction.sender,
        to_canonical_address,
        functools.partial(generate_contract_address, nonce=0),
    )


@pytest.fixture
def vmc():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    # provider = HTTPProvider('http://localhost:8545')
    w3 = Web3(provider)

    # setup vmc's web3.eth.contract instance
    vmc_tx = create_vmc_tx(
        SpuriousDragonTransaction,
        get_sharding_config()['GAS_PRICE'],
    )
    vmc_addr = get_contract_address_from_contract_tx(vmc_tx)
    vmc_json = get_vmc_json()
    vmc_abi = vmc_json['abi']
    vmc_bytecode = vmc_json['bytecode']
    VMCClass = VMC.factory(w3, abi=vmc_abi, bytecode=vmc_bytecode)
    test_keys = get_default_account_keys()
    vmc_handler = VMCClass(to_checksum_address(vmc_addr), default_privkey=test_keys[0])
    vmc_handler.vmc_tx_sender_address = vmc_tx.sender
    return vmc_handler
