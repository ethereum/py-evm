# Imitate tests/core/chain-object/test_chain_retrieval_of_vm_class.py

import pytest

from eth.beacon.chains.base import (
    BeaconChain,
)
from eth.beacon.exceptions import (
    SMNotFound,
)
from eth.beacon.state_machines.base import (
    BeaconStateMachine,
)


class BaseSMForTesting(BeaconStateMachine):
    @classmethod
    def create_block_from_parent(cls, parent_block, **block_params):
        pass


class SM_A(BaseSMForTesting):
    pass


class SM_B(SM_A):
    pass


class ChainForTesting(BeaconChain):
    sm_configuration = (
        (0, SM_A),
        (10, SM_B),
    )


def test_simple_chain(base_db, genesis_block):
    chain = ChainForTesting.from_genesis_block(base_db, genesis_block)

    assert chain.get_sm_class_for_block_slot(0) is SM_A

    for num in range(1, 10):
        assert chain.get_sm_class_for_block_slot(num) is SM_A

    assert chain.get_sm_class_for_block_slot(10) is SM_B

    for num in range(11, 100, 5):
        assert chain.get_sm_class_for_block_slot(num) is SM_B


def test_vm_not_found_if_no_matching_block_number(genesis_block):
    chain_class = BeaconChain.configure('ChainStartsAtBlock10', sm_configuration=(
        (10, SM_A),
    ))
    with pytest.raises(SMNotFound):
        chain_class.get_sm_class_for_block_slot(9)
