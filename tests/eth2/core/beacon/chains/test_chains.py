import pytest

from eth2.beacon.chains.testnet import TestnetChain as _TestnetChain


@pytest.mark.parametrize("chain_klass", (_TestnetChain,))
def test_chain_class_well_defined(base_db, chain_klass, empty_attestation_pool, config):
    chain = chain_klass(base_db, empty_attestation_pool, config)
    assert chain.sm_configuration is not () and chain.sm_configuration is not None
