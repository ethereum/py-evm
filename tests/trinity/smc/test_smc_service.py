import asyncio
import secrets

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

from evm.rlp.headers import (
    CollationHeader,
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


def get_current_period(w3):
    block = w3.eth.blockNumber
    period = block // sharding_config["PERIOD_LENGTH"]
    return period


def add_header(w3, smc_handler, shard_id):
    header = CollationHeader(
        shard_id=shard_id,
        period=get_current_period(w3),
        chunk_root=secrets.token_bytes(32),
        proposer_address=smc_handler.private_key.public_key.to_canonical_address(),
    )
    smc_handler.add_header(
        shard_id=header.shard_id,
        chunk_root=header.chunk_root,
        period=header.period,
    )
    return header


@pytest.fixture()
def w3():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)

    # fast forward to next period so that we can add headers which is not possible in period 0
    w3.testing.mine(sharding_config["PERIOD_LENGTH"])

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
    smc_service.polling_interval = 0.1  # makes tests run faster
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
async def test_header_subscription(w3, smc_service, smc_handler):
    subscription = smc_service.subscribe(0)
    header = add_header(shard_id=0, w3=w3, smc_handler=smc_handler)
    w3.testing.mine()

    await asyncio.sleep(smc_service.polling_interval)

    assert subscription.added_header_queue.qsize() == 1
    received_header = subscription.added_header_queue.get_nowait()
    assert received_header == header


@pytest.mark.asyncio
async def test_header_subscription_wrong_shard(w3, smc_service, smc_handler):
    subscription = smc_service.subscribe(0)
    add_header(shard_id=1, w3=w3, smc_handler=smc_handler)

    await asyncio.sleep(smc_service.polling_interval)

    assert subscription.added_header_queue.empty()


@pytest.mark.asyncio
async def test_header_subscription_multiple_headers(w3, smc_service, smc_handler):
    subscription = smc_service.subscribe(0)

    header1 = add_header(shard_id=0, w3=w3, smc_handler=smc_handler)
    w3.testing.mine(sharding_config["PERIOD_LENGTH"])
    header2 = add_header(shard_id=0, w3=w3, smc_handler=smc_handler)
    w3.testing.mine()

    await asyncio.sleep(smc_service.polling_interval)

    assert subscription.added_header_queue.qsize() == 2
    received_headers = [subscription.added_header_queue.get_nowait() for _ in range(2)]
    assert received_headers == [header1, header2]


@pytest.mark.asyncio
async def test_header_subscription_multiple_shards(w3, smc_service, smc_handler):
    shard_ids = [1, 0]
    subscriptions = [smc_service.subscribe(shard_id) for shard_id in shard_ids]

    header1 = add_header(shard_id=shard_ids[0], w3=w3, smc_handler=smc_handler)
    w3.testing.mine()  # mine tx independently so that different nonces are used
    header2 = add_header(shard_id=shard_ids[1], w3=w3, smc_handler=smc_handler)
    w3.testing.mine()

    await asyncio.sleep(smc_service.polling_interval)

    for header, subscription in zip([header1, header2], subscriptions):
        assert subscription.added_header_queue.qsize() == 1
        received_header = subscription.added_header_queue.get_nowait()
        assert received_header == header


@pytest.mark.asyncio
async def test_header_subscription_multiple_subscribers(w3, smc_service, smc_handler):
    subscriptions = [smc_service.subscribe(0) for _ in range(2)]

    header = add_header(shard_id=0, w3=w3, smc_handler=smc_handler)
    w3.testing.mine()

    await asyncio.sleep(smc_service.polling_interval)

    for subscription in subscriptions:
        assert subscription.added_header_queue.qsize() == 1
        received_header = subscription.added_header_queue.get_nowait()
        assert received_header == header


@pytest.mark.asyncio
async def test_header_subscription_unsubscribe(w3, smc_service, smc_handler):
    subscription = smc_service.subscribe(0)

    header = add_header(shard_id=0, w3=w3, smc_handler=smc_handler)
    w3.testing.mine(sharding_config["PERIOD_LENGTH"])
    await asyncio.sleep(smc_service.polling_interval)

    smc_service.unsubscribe(subscription)
    add_header(shard_id=0, w3=w3, smc_handler=smc_handler)
    w3.testing.mine()

    assert subscription.added_header_queue.qsize() == 1
    received_header = subscription.added_header_queue.get_nowait()
    assert received_header == header


@pytest.mark.asyncio
async def test_add_header(w3, smc_service, smc_handler):
    subscription = smc_service.subscribe(0)

    chunk_root = secrets.token_bytes(32)
    proposer = smc_service.private_key.public_key.to_canonical_address()
    period = w3.eth.blockNumber // sharding_config["PERIOD_LENGTH"]
    smc_service.add_header(0, chunk_root)
    w3.testing.mine()

    await asyncio.sleep(smc_service.polling_interval)

    assert subscription.added_header_queue.qsize() == 1
    received_header = subscription.added_header_queue.get_nowait()

    assert received_header.shard_id == 0
    assert received_header.period == period
    assert received_header.chunk_root == chunk_root
    assert received_header.proposer_address == proposer
