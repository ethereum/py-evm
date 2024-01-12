from eth_keys import (
    keys,
)
import pytest

from eth.chains.base import (
    MiningChain,
)
from eth.chains.mainnet import (
    MINING_MAINNET_VMS,
)
from eth.tools.builder.chain import (
    api,
)


@pytest.fixture(params=MINING_MAINNET_VMS)
def chain(request):
    return api.build(
        MiningChain,
        api.fork_at(request.param, 0),
        api.disable_pow_check(),
        api.genesis(),
    )


@pytest.fixture
def sender():
    return keys.PrivateKey(b"unicornsrainbows" * 2)


TO_ADDRESS = b"\0" * 20


@pytest.fixture
def basic_transaction(chain, sender):
    unsigned_txn = chain.create_unsigned_transaction(
        nonce=0,
        gas_price=1234,
        gas=21001,  # non-default for testing purposes
        to=TO_ADDRESS,
        value=4321,
        data=b"test",
    )
    return unsigned_txn.as_signed_transaction(sender)


def test_basic_create_transaction(chain, basic_transaction):
    transaction = chain.create_transaction(
        nonce=basic_transaction.nonce,
        gas_price=basic_transaction.gas_price,
        gas=basic_transaction.gas,
        to=basic_transaction.to,
        value=basic_transaction.value,
        data=basic_transaction.data,
        v=basic_transaction.v,
        r=basic_transaction.r,
        s=basic_transaction.s,
    )
    assert transaction == basic_transaction


def test_basic_create_unsigned_transaction(chain):
    transaction = chain.create_unsigned_transaction(
        nonce=0,
        gas_price=1234,
        gas=21001,
        to=TO_ADDRESS,
        value=4321,
        data=b"test",
    )
    assert transaction.nonce == 0
    assert transaction.gas_price == 1234
    assert transaction.gas == 21001
    assert transaction.to == TO_ADDRESS
    assert transaction.value == 4321
    assert transaction.data == b"test"
