import pytest

from eth_utils import (
    decode_hex,
    to_canonical_address,
)

from eth_keys import KeyAPI

from evm import Chain
from evm import constants
from evm.db import get_db_backend
from evm.db.chain import ChainDB
from evm.db.state import FlatTrieBackend
from evm.vm.forks.frontier import FrontierVM
from evm.vm.forks.sharding import ShardingVM


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
def chain(chaindb, funded_address, funded_address_initial_balance):
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
        name='TestChain',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, FrontierVM),
        ))
    chain = klass.from_genesis(chaindb, genesis_params, genesis_state)
    return chain


@pytest.fixture
def shard_chain(chaindb, funded_address, funded_address_initial_balance):
    shard_chaindb = ChainDB(get_db_backend(), state_backend_class=FlatTrieBackend)
    return chain(shard_chaindb, funded_address, funded_address_initial_balance)


@pytest.fixture
def shard_chain_without_block_validation(funded_addr):
    """
    Return a Chain object containing just the genesis block.

    This Chain does not perform any validation when importing new blocks.

    The Chain's state includes one funded account specified by the `funded_addr` argument.

    You can then deploy contract to the funded account.
    """
    shard_chaindb = ChainDB(get_db_backend(), state_backend_class=FlatTrieBackend)
    overrides = {
        'import_block': import_block_without_validation,
        'validate_block': lambda self, block: None,
    }
    klass = Chain.configure(
        name='TestShardChainWithoutBlockValidation',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, ShardingVM),
        ),
        **overrides,
    )
    initial_balance = 100000000
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
        'state_root': decode_hex(
            '0x9d354f9b5ba851a35eced279ef377111387197581429cfcc7f744ef89a30b5d4')
    }
    genesis_state = {
        funded_addr: {
            'balance': initial_balance,
            'nonce': 0,
            'code': b'',
            'storage': {},
        }
    }
    chain = klass.from_genesis(shard_chaindb, genesis_params, genesis_state)
    chain.funded_address = funded_addr
    chain.funded_address_initial_balance = initial_balance
    return chain


@pytest.fixture
def chain_without_block_validation(
        chaindb,
        funded_address,
        funded_address_initial_balance):
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
        name='TestChainWithoutBlockValidation',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, FrontierVM),
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
