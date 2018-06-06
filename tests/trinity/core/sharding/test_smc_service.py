import asyncio

import pytest

from cytoolz import (
    merge,
)

from web3 import (
    Web3,
    EthereumTesterProvider,
)
from eth_tester import (
    EthereumTester,
    PyEVMBackend,
)
from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from sharding.handler.smc_handler import (
    SMCHandler as SMCHandlerFactory,
)
from sharding.contracts.utils.config import (
    get_sharding_config,
)

from trinity.smc_service import (
    SMCService,
)


smc_constructor_kwargs = {
    "_SHARD_COUNT": 2,
    "_PERIOD_LENGTH": 5,
    "_LOOKAHEAD_LENGTH": 4,
    "_COMMITTEE_SIZE": 6,
    "_QUORUM_SIZE": 4,
    "_NOTARY_DEPOSIT": 1,
    "_NOTARY_LOCKUP_LENGTH": 30,
}

sharding_config = merge(
    get_sharding_config(),
    {
        config_key: smc_constructor_kwargs[constructor_key] for config_key, constructor_key in [
            ("SHARD_COUNT", "_SHARD_COUNT"),
            ("PERIOD_LENGTH", "_PERIOD_LENGTH"),
            ("LOOKAHEAD_PERIODS", "_LOOKAHEAD_LENGTH"),
            ("COMMITTEE_SIZE", "_COMMITTEE_SIZE"),
            ("QUORUM_SIZE", "_QUORUM_SIZE"),
            ("NOTARY_DEPOSIT", "_NOTARY_DEPOSIT"),
            ("NOTARY_LOCKUP_LENGTH", "_NOTARY_LOCKUP_LENGTH"),
        ]
    }
)


@pytest.fixture()
def w3():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    return w3


@pytest.fixture()
def smc_address(w3):
    SMCHandler = w3.eth.contract(ContractFactoryClass=SMCHandlerFactory)
    deployment_tx_hash = SMCHandler.constructor(**smc_constructor_kwargs).transact()
    w3.testing.mine()
    deployment_receipt = w3.eth.getTransactionReceipt(deployment_tx_hash)
    assert deployment_receipt is not None
    return deployment_receipt.contractAddress


@pytest.fixture()
def private_keys():
    return iter(get_default_account_keys())


@pytest.fixture()
async def smc_service(w3, smc_address, private_keys):
    smc_service = SMCService(
        w3=w3,
        smc_address=smc_address,
        sharding_config=sharding_config,
        private_key=next(private_keys)
    )
    asyncio.ensure_future(smc_service.run())

    yield smc_service

    await smc_service.cancel()


@pytest.fixture()
def smc_handler(w3, smc_address, private_keys):
    return SMCHandlerFactory.factory(web3=w3)(
        smc_address,
        config=sharding_config,
        private_key=next(private_keys),
    )


@pytest.mark.asyncio
async def test(w3, smc_service, smc_handler):
    pass
