import pytest

from eth2.beacon.chains.base import BeaconChain


def _beacon_chain_with_block_validation(
    base_db,
    genesis_block,
    genesis_state,
    fixture_sm_class,
    config,
    chain_cls=BeaconChain,
):
    """
    Return a Chain object containing just the genesis block.

    The Chain's state includes one funded account, which can be found in the
    funded_address in the chain itself.

    This Chain will perform all validations when importing new blocks, so only
    valid and finalized blocks can be used with it. If you want to test
    importing arbitrarily constructe, not finalized blocks, use the
    chain_without_block_validation fixture instead.
    """

    klass = chain_cls.configure(
        __name__="TestChain",
        sm_configuration=((genesis_state.slot, fixture_sm_class),),
        chain_id=5566,
    )

    chain = klass.from_genesis(base_db, genesis_state, genesis_block, config)
    return chain


@pytest.fixture
def beacon_chain_with_block_validation(
    base_db, genesis_block, genesis_state, fixture_sm_class, config
):
    return _beacon_chain_with_block_validation(
        base_db, genesis_block, genesis_state, fixture_sm_class, config
    )


def import_block_without_validation(chain, block):
    return super(type(chain), chain).import_block(block, perform_validation=False)


@pytest.fixture(params=[BeaconChain])
def beacon_chain_without_block_validation(
    request, base_db, genesis_state, genesis_block, fixture_sm_class
):
    """
    Return a Chain object containing just the genesis block.

    This Chain does not perform any validation when importing new blocks.

    The Chain's state includes one funded account and a private key for it,
    which can be found in the funded_address and private_keys variables in the
    chain itself.
    """
    # Disable block validation so that we don't need to construct finalized blocks.
    overrides = {"import_block": import_block_without_validation}
    chain_class = request.param
    klass = chain_class.configure(
        __name__="TestChainWithoutBlockValidation",
        sm_configuration=((0, fixture_sm_class),),
        chain_id=5566,
        **overrides,
    )

    chain = klass.from_genesis(base_db, genesis_state, genesis_block)
    return chain
