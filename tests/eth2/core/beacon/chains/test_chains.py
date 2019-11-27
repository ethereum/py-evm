import pytest

from eth2.beacon.chains.testnet import SkeletonLakeChain


@pytest.mark.parametrize("chain_klass", (SkeletonLakeChain,))
def test_chain_class_well_defined(base_db, chain_klass, config):
    chain = chain_klass(base_db, config)
    assert chain.sm_configuration is not () and chain.sm_configuration is not None
