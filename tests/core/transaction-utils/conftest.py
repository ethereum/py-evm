import pytest


# from https://github.com/ethereum/tests/blob/c951a3c105d600ccd8f1c3fc87856b2bcca3df0a/BasicTests/txtest.json  # noqa: E501
TRANSACTION_FIXTURES = [
    {
        "chainId": None,
        "key": "c85ef7d79691fe79573b1a7064c19c1a9819ebdbd1faaab1a8ec92344438aaf4",
        "nonce": 0,
        "gasPrice": 1000000000000,
        "gas": 10000,
        "to": "13978aee95f38490e9769c39b2773ed763d9cd5f",
        "value": 10000000000000000,
        "data": "",
        "signed": "f86b8085e8d4a510008227109413978aee95f38490e9769c39b2773ed763d9cd5f872386f26fc10000801ba0eab47c1a49bf2fe5d40e01d313900e19ca485867d462fe06e139e3a536c6d4f4a014a569d327dcda4b29f74f93c0e9729d2f49ad726e703f9cd90dbb0fbf6649f1"  # noqa: E501
    },
    {
        "chainId": None,
        "key": "c87f65ff3f271bf5dc8643484f66b200109caffe4bf98c4cb393dc35740b28c0",
        "nonce": 0,
        "gasPrice": 1000000000000,
        "gas": 10000,
        "to": "",
        "value": 0,
        "data": "6025515b525b600a37f260003556601b596020356000355760015b525b54602052f260255860005b525b54602052f2",  # noqa: E501
        "signed": "f87f8085e8d4a510008227108080af6025515b525b600a37f260003556601b596020356000355760015b525b54602052f260255860005b525b54602052f21ba05afed0244d0da90b67cf8979b0f246432a5112c0d31e8d5eedd2bc17b171c694a0bb1035c834677c2e1185b8dc90ca6d1fa585ab3d7ef23707e1a497a98e752d1b"  # noqa: E501
    },
    {
        "chainId": 1,
        "key": "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318",
        "nonce": 0,
        "gasPrice": 234567897654321,
        "gas": 2000000,
        "to": "0xF0109fC8DF283027b6285cc889F5aA624EaC1F55",
        "value": 1000000000,
        "data": "",
        "signed": "0xf86a8086d55698372431831e848094f0109fc8df283027b6285cc889f5aa624eac1f55843b9aca008025a009ebb6ca057a0535d6186462bc0b465b561c94a295bdb0621fc19208ab149a9ca0440ffd775ce91a833ab410777204d5341a6f9fa91216a6f3ee2c051fea6a0428",  # noqa: E501
    },
]


SHARDING_TRANSACTION_FIXTURES = [
    {
        "chain_id": 1,
        "shard_id": 1,
        "to": "0x2863c51de9fcb96542a07186fe3aeda6bb8a116d",
        # rlp-encoded of [destination, value, msg_data, vrs]
        # below example is
        # rlp.encode([
        #     b'82df0950f5a951637e0307cdcb4c672f298b8bc6',
        #     1000000,
        #     b'',
        #     b'\x01\x02\x03'
        # ])
        # in hex
        "data": "0xf2a838326466303935306635613935313633376530333037636463623463363732663239386238626336830f42408083010203",  # noqa: E501
        "gas": 2000000,
        "gas_price": 1000000000000,
        "access_list": "",
        "code": "",
        "intrensic_gas": 24468,
    },
    {
        "chain_id": 1,
        "shard_id": 3,
        "to": "0x2863c51de9fcb96542a07186fe3aeda6bb8a116d",
        "data": "0xf3a83434346662353861383037656634633936303362373834383637336637653361363865623134613580836000f38400000001",  # noqa: E501
        "gas": 2000000,
        "gas_price": 1000000000000,
        "access_list": "",
        "code": "0x6060604052341561000f57600080fd5b5b60ca8061001e6000396000f30060606040526000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff168063500d6847146047578063cd580ff314606d575b600080fd5b3415605157600080fd5b6057608d565b6040518082815260200191505060405180910390f35b3415607757600080fd5b608b60048080359060200190919050506093565b005b60005481565b806000819055505b505600a165627a7a7230582080a774dd085c3fe22daee6e793ecd8ed1d4edebd37b2a82fbab37f5f1aacf2a80029",  # noqa: E501
        "intrensic_gas": 37304,
    },
]


@pytest.fixture(params=range(len(TRANSACTION_FIXTURES)))
def txn_fixture(request):
    return TRANSACTION_FIXTURES[request.param]


@pytest.fixture(params=range(len(SHARDING_TRANSACTION_FIXTURES)))
def sharding_txn_fixture(request):
    return SHARDING_TRANSACTION_FIXTURES[request.param]
