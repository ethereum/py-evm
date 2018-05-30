import pytest


from evm import Chain
from evm import constants
# TODO: tests should not be locked into one set of VM rules.  Look at expanding
# to all mainnet vms.
from evm.vm.forks.spurious_dragon import SpuriousDragonVM


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
    SpuriousDragonVMForTesting = SpuriousDragonVM.configure(validate_seal=lambda self, block: None)
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
