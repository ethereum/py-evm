import pytest
from eth2.beacon.chains.testnet import TestnetChain


@pytest.mark.parametrize(
    "chain_klass",
    (
        TestnetChain,
    )
)
def test_chain_class_well_defined(base_db,
                                  chain_klass):
    chain = chain_klass(base_db)
    assert chain.sm_configuration is not () and chain.sm_configuration is not None
