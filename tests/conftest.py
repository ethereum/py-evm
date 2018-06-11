import logging
import sys

# from evm.utils.logging import TRACE_LEVEL_NUM

import pytest

from eth_utils import (
    decode_hex,
    to_canonical_address,
    to_wei,
)
from eth_keys import keys

from evm import Chain
from evm import constants
from evm.db.backends.memory import MemoryDB
# TODO: tests should not be locked into one set of VM rules.  Look at expanding
# to all mainnet vms.
from evm.vm.forks.spurious_dragon import SpuriousDragonVM


@pytest.fixture(autouse=True, scope="session")
def vm_logger():
    logger = logging.getLogger('evm')

    handler = logging.StreamHandler(sys.stdout)

    # level = TRACE_LEVEL_NUM
    # level = logging.DEBUG
    # level = logging.INFO
    level = logging.ERROR

    logger.setLevel(level)
    handler.setLevel(level)

    logger.addHandler(handler)

    return logger


# Uncomment this to have logs from tests written to a file.  This is useful for
# debugging when you need to dump the VM output from test runs.
"""
@pytest.yield_fixture(autouse=True)
def vm_file_logger(request):
    import datetime
    import os

    logger = logging.getLogger('evm')

    level = TRACE_LEVEL_NUM
    #level = logging.DEBUG
    #level = logging.INFO

    logger.setLevel(level)

    fixture_data = request.getfuncargvalue('fixture_data')
    fixture_path = fixture_data[0]
    logfile_name = 'logs/{0}-{1}.log'.format(
        '-'.join(
            [os.path.basename(fixture_path)] +
            [str(value) for value in fixture_data[1:]]
        ),
        datetime.datetime.now().isoformat(),
    )

    with open(logfile_name, 'w') as logfile:
        handler = logging.StreamHandler(logfile)
        logger.addHandler(handler)
        try:
            yield logger
        finally:
            logger.removeHandler(handler)
"""


@pytest.fixture
def base_db():
    return MemoryDB()


@pytest.fixture
def funded_address_private_key():
    return keys.PrivateKey(
        decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8')
    )


@pytest.fixture
def funded_address(funded_address_private_key):
    return funded_address_private_key.public_key.to_canonical_address()


@pytest.fixture
def funded_address_initial_balance():
    return to_wei(1000, 'ether')


@pytest.fixture
def chain_with_block_validation(base_db, funded_address, funded_address_initial_balance):
    """
    Return a Chain object containing just the genesis block.

    The Chain's state includes one funded account, which can be found in the
    funded_address in the chain itself.

    This Chain will perform all validations when importing new blocks, so only
    valid and finalized blocks can be used with it. If you want to test
    importing arbitrarily constructe, not finalized blocks, use the
    chain_without_block_validation fixture instead.
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
        ),
        network_id=1337,
    )
    chain = klass.from_genesis(base_db, genesis_params, genesis_state)
    return chain


def import_block_without_validation(chain, block):
    return Chain.import_block(chain, block, perform_validation=False)


@pytest.fixture
def chain_without_block_validation(base_db, funded_address, funded_address_initial_balance):
    """
    Return a Chain object containing just the genesis block.

    This Chain does not perform any validation when importing new blocks.

    The Chain's state includes one funded account and a private key for it,
    which can be found in the funded_address and private_keys variables in the
    chain itself.
    """
    # Disable block validation so that we don't need to construct finalized blocks.
    overrides = {
        'import_block': import_block_without_validation,
        'validate_block': lambda self, block: None,
    }
    SpuriousDragonVMForTesting = SpuriousDragonVM.configure(validate_seal=lambda block: None)
    klass = Chain.configure(
        __name__='TestChainWithoutBlockValidation',
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, SpuriousDragonVMForTesting),
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
    chain = klass.from_genesis(base_db, genesis_params, genesis_state)
    return chain
