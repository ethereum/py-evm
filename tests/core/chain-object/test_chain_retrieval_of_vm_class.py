import pytest


from evm import Chain
from evm.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
    GENESIS_GAS_LIMIT,
)
from evm.db.backends.memory import MemoryDB
from evm.db.chain import ChainDB
from evm.exceptions import (
    VMNotFound,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.vm.base import VM


@pytest.fixture
def genesis_header():
    return BlockHeader(
        difficulty=GENESIS_DIFFICULTY,
        block_number=GENESIS_BLOCK_NUMBER,
        gas_limit=GENESIS_GAS_LIMIT,
    )


class BaseVMForTesting(VM):
    @classmethod
    def create_header_from_parent(cls, parent_header, **header_params):
        pass


class VM_A(BaseVMForTesting):
    pass


class VM_B(VM_A):
    pass


class ChainForTesting(Chain):
    vm_configuration = (
        (0, VM_A),
        (10, VM_B),
    )


@pytest.fixture()
def base_db():
    return MemoryDB()


@pytest.fixture()
def chaindb(base_db):
    return ChainDB(base_db)


def test_header_chain_get_vm_class_for_block_number(base_db, genesis_header):
    chain = ChainForTesting.from_genesis_header(base_db, genesis_header)

    assert chain.get_vm_class_for_block_number(0) is VM_A

    for num in range(1, 10):
        assert chain.get_vm_class_for_block_number(num) is VM_A

    assert chain.get_vm_class_for_block_number(10) is VM_B

    for num in range(11, 100, 5):
        assert chain.get_vm_class_for_block_number(num) is VM_B


def test_header_chain_invalid_if_no_vm_configuration(base_db, genesis_header):
    chain_class = Chain.configure('ChainNoEmptyConfiguration', vm_configuration=())
    with pytest.raises(ValueError):
        chain_class(base_db, genesis_header)


def test_vm_not_found_if_no_matching_block_number(genesis_header):
    chain_class = Chain.configure('ChainStartsAtBlock10', vm_configuration=(
        (10, VM_A),
    ))
    with pytest.raises(VMNotFound):
        chain_class.get_vm_class_for_block_number(9)
