import os

import json

import pytest

from eth_utils import (
    decode_hex,
    to_canonical_address,
)
from eth_keys import KeyAPI
from trie import (
    BinaryTrie,
)

from evm import Chain
from evm import constants
from evm.chains.shard import (
    Shard,
)
from evm.db import get_db_backend
from evm.db.chain import ChainDB
from evm.db.state import (
    ShardingAccountStateDB
)
from evm.vm.forks.sharding import ShardingVM
from evm.vm.forks.spurious_dragon import SpuriousDragonVM


# This block is a child of the genesis defined in the chain fixture above and contains a single tx
# that transfers 10 wei from 0xa94f5374fce5edbc8e2a8697c15331677e6ebf0b to
# 0x095e7baea6a6c7c4c2dfeb977efac326af552d87.
valid_block_rlp = decode_hex(
    "0xf90260f901f9a07285abd5b24742f184ad676e31f6054663b3529bc35ea2fcad8a3e0f642a46f7a01dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347948888f1f195afa192cfee860698584c030f4c9db1a0964e6c9995e7e3757e934391b4f16b50c20409ee4eb9abd4c4617cb805449b9aa053d5b71a8fbb9590de82d69dfa4ac31923b0c8afce0d30d0d8d1e931f25030dca0bc37d79753ad738a6dac4921e57392f145d8887476de3f783dfa7edae9283e52b90100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008302000001832fefd8825208845754132380a0194605bacef646779359318c7b5899559a5bf4074bbe2cfb7e1b83b1504182dd88e0205813b22e5a9cf861f85f800a82c35094095e7baea6a6c7c4c2dfeb977efac326af552d870a801ba0f3266921c93d600c43f6fa4724b7abae079b35b9e95df592f95f9f3445e94c88a012f977552ebdb7a492cf35f3106df16ccb4576ebad4113056ee1f52cbe4978c1c0")  # noqa: E501


def import_block_without_validation(chain, block):
    return Chain.import_block(chain, block, perform_validation=False)


@pytest.fixture
def funded_address_private_key():
    return KeyAPI().PrivateKey(
        decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8')
    )


@pytest.fixture
def funded_address(funded_address_private_key):  # noqa: F811
    return funded_address_private_key.public_key.to_canonical_address()


@pytest.fixture
def funded_address_initial_balance():
    return 10000000000


@pytest.fixture
def chaindb():
    return ChainDB(get_db_backend())


@pytest.fixture
def shard_chaindb():
    return ChainDB(
        get_db_backend(),
        account_state_class=ShardingAccountStateDB,
        trie_class=BinaryTrie,
    )


@pytest.fixture
def chain(chaindb, funded_address, funded_address_initial_balance):  # noqa: F811
    """
    Return a Chain object containing just the genesis block.

    The Chain's state includes one funded account, which can be found in the funded_address in the
    chain itself.

    This Chain will perform all validations when importing new blocks, so only valid and finalized
    blocks can be used with it. If you want to test importing arbitrarily constructe, not
    finalized blocks, use the chain_without_block_validation fixture instead.
    """
    genesis_params = {
        "bloom": 0,
        "coinbase": to_canonical_address("8888f1f195afa192cfee860698584c030f4c9db1"),
        "difficulty": 131072,
        "extra_data": b"B",
        "gas_limit": 3141592,
        "gas_used": 0,
        "mix_hash": decode_hex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"),  # noqa: E501
        "nonce": decode_hex("0102030405060708"),
        "block_number": 0,
        "parent_hash": decode_hex("0000000000000000000000000000000000000000000000000000000000000000"),  # noqa: E501
        "receipt_root": decode_hex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"),  # noqa: E501
        "timestamp": 1422494849,
        "transaction_root": decode_hex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"),  # noqa: E501
        "uncles_hash": decode_hex("1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347")  # noqa: E501
    }
    genesis_state = {
        funded_address: {
            "balance": funded_address_initial_balance,
            "nonce": 0,
            "code": b"",
            "storage": {}
        }
    }
    klass = Chain.configure(
        __name__='TestChain',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, SpuriousDragonVM),
        ))
    chain = klass.from_genesis(chaindb, genesis_params, genesis_state)
    return chain


PAYGAS_contracts = json.load(
    open(os.path.join(os.path.dirname(__file__), './contract_fixtures/PAYGAS_contracts.json'))
)


CREATE2_contracts = json.load(
    open(os.path.join(os.path.dirname(__file__), './contract_fixtures/CREATE2_contracts.json'))
)


nonce_tracking_contracts = json.load(
    open(
        os.path.join(os.path.dirname(__file__), './contract_fixtures/nonce_tracking_contracts.json')
    )
)


SHARD_CHAIN_CONTRACTS_FIXTURES = [
    {
        "contract_code": CREATE2_contracts['simple_transfer_contract']['bytecode'],
        "deployed_address": CREATE2_contracts['simple_transfer_contract']['address'],
        "initial_balance": funded_address_initial_balance(),
    },
    {
        "contract_code": CREATE2_contracts['CREATE2_contract']['bytecode'],
        "deployed_address": CREATE2_contracts['CREATE2_contract']['address'],
        "initial_balance": funded_address_initial_balance(),
    },
    {
        "contract_code": PAYGAS_contracts['PAYGAS_contract_normal']['bytecode'],
        "deployed_address": PAYGAS_contracts['PAYGAS_contract_normal']['address'],
        "initial_balance": funded_address_initial_balance(),
    },
    {
        "contract_code": PAYGAS_contracts['simple_forwarder_contract']['bytecode'],
        "deployed_address": PAYGAS_contracts['simple_forwarder_contract']['address'],
        "initial_balance": funded_address_initial_balance(),
    },
    {
        "contract_code": PAYGAS_contracts['PAYGAS_contract_triggered_twice']['bytecode'],
        "deployed_address": PAYGAS_contracts['PAYGAS_contract_triggered_twice']['address'],
        "initial_balance": funded_address_initial_balance(),
    },
    {
        "contract_code": nonce_tracking_contracts['nonce_tracking_contract']['bytecode'],
        "deployed_address": nonce_tracking_contracts['nonce_tracking_contract']['address'],
        "initial_balance": funded_address_initial_balance(),
    },
    {
        "contract_code": nonce_tracking_contracts['no_nonce_tracking_contract']['bytecode'],
        "deployed_address": nonce_tracking_contracts['no_nonce_tracking_contract']['address'],
        "initial_balance": funded_address_initial_balance(),
    },
]


@pytest.fixture
def shard_chain(shard_chaindb, funded_address, funded_address_initial_balance):  # noqa: F811
    genesis_params = {
        "bloom": 0,
        "coinbase": to_canonical_address("8888f1f195afa192cfee860698584c030f4c9db1"),
        "difficulty": 131072,
        "extra_data": b"B",
        "gas_limit": 3141592,
        "gas_used": 0,
        "mix_hash": decode_hex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"),  # noqa: E501
        "nonce": decode_hex("0102030405060708"),
        "block_number": 0,
        "parent_hash": decode_hex("0000000000000000000000000000000000000000000000000000000000000000"),  # noqa: E501
        "transaction_root": constants.EMPTY_SHA3,
        "receipt_root": constants.EMPTY_SHA3,
        "timestamp": 1422494849,
        "uncles_hash": decode_hex("1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347")  # noqa: E501
    }
    genesis_state = {
        funded_address: {
            "balance": funded_address_initial_balance,
            "nonce": 0,
            "code": b"",
            "storage": {}
        }
    }
    klass = Shard.configure(
        __name__='TestChain',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, ShardingVM),
        ))
    shard = klass.from_genesis(shard_chaindb, genesis_params, genesis_state)

    return shard


@pytest.fixture
def shard_chain_without_block_validation(shard_chaindb):  # noqa: F811
    shard_chaindb = shard_chaindb
    """
    Return a Chain object containing just the genesis block.

    This Chain does not perform any validation when importing new blocks.

    The Chain's state includes one funded account which is where the simple transfer

    contract will be deployed at.
    """
    overrides = {
        'import_block': import_block_without_validation,
        'validate_block': lambda self, block: None,
    }
    klass = Shard.configure(
        __name__='TestShardChainWithoutBlockValidation',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, ShardingVM),
        ),
        **overrides,
    )
    genesis_params = {
        'block_number': constants.GENESIS_BLOCK_NUMBER,
        'difficulty': constants.GENESIS_DIFFICULTY,
        'gas_limit': constants.GENESIS_GAS_LIMIT,
        'parent_hash': constants.GENESIS_PARENT_HASH,
        'coinbase': constants.GENESIS_COINBASE,
        'nonce': constants.GENESIS_NONCE,
        'mix_hash': constants.GENESIS_MIX_HASH,
        'extra_data': constants.GENESIS_EXTRA_DATA,
        'timestamp': 1501851927,
        'transaction_root': constants.EMPTY_SHA3,
        'receipt_root': constants.EMPTY_SHA3,
    }
    genesis_state = {
        decode_hex(SHARD_CHAIN_CONTRACTS_FIXTURES[i]["deployed_address"]): {
            'balance': SHARD_CHAIN_CONTRACTS_FIXTURES[i]["initial_balance"],
            'code': b'',
            'storage': {},
        } for i in range(len(SHARD_CHAIN_CONTRACTS_FIXTURES))
    }
    shard = klass.from_genesis(shard_chaindb, genesis_params, genesis_state)
    return shard


@pytest.fixture
def chain_without_block_validation(
        chaindb,
        funded_address,
        funded_address_initial_balance):  # noqa: F811
    """
    Return a Chain object containing just the genesis block.

    This Chain does not perform any validation when importing new blocks.

    The Chain's state includes one funded account and a private key for it, which can be found in
    the funded_address and private_keys variables in the chain itself.
    """
    # Disable block validation so that we don't need to construct finalized blocks.
    overrides = {
        'import_block': import_block_without_validation,
        'validate_block': lambda self, block: None,
    }
    klass = Chain.configure(
        __name__='TestChainWithoutBlockValidation',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, SpuriousDragonVM),
        ),
        **overrides,
    )
    genesis_params = {
        'block_number': constants.GENESIS_BLOCK_NUMBER,
        'difficulty': constants.GENESIS_DIFFICULTY,
        'gas_limit': constants.GENESIS_GAS_LIMIT,
        'parent_hash': constants.GENESIS_PARENT_HASH,
        'coinbase': constants.GENESIS_COINBASE,
        'nonce': constants.GENESIS_NONCE,
        'mix_hash': constants.GENESIS_MIX_HASH,
        'extra_data': constants.GENESIS_EXTRA_DATA,
        'timestamp': 1501851927,
    }
    genesis_state = {
        funded_address: {
            'balance': funded_address_initial_balance,
            'nonce': 0,
            'code': b'',
            'storage': {},
        }
    }
    chain = klass.from_genesis(chaindb, genesis_params, genesis_state)
    return chain
