import pytest

from evm import constants
from evm import EVM

from evm.exceptions import (
    EVMNotFound,
    ValidationError,
)
from evm.vm.flavors.frontier import FrontierVM
from evm.vm.flavors.homestead import HomesteadVM


def test_get_vm_class_for_block_number():
    evm = EVM.configure(
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, FrontierVM),
            (constants.HOMESTEAD_MAINNET_BLOCK, HomesteadVM),
        ),
    )
    assert evm.get_vm_class_for_block_number(
        constants.GENESIS_BLOCK_NUMBER,) == FrontierVM
    assert evm.get_vm_class_for_block_number(
        constants.HOMESTEAD_MAINNET_BLOCK - 1) == FrontierVM
    assert evm.get_vm_class_for_block_number(
        constants.HOMESTEAD_MAINNET_BLOCK) == HomesteadVM
    assert evm.get_vm_class_for_block_number(
        constants.HOMESTEAD_MAINNET_BLOCK + 1) == HomesteadVM


def test_get_vm_class_for_block_number_evm_not_found():
    evm = EVM.configure(vm_configuration=())
    with pytest.raises(EVMNotFound):
        evm.get_vm_class_for_block_number(constants.GENESIS_BLOCK_NUMBER)


def test_configure_invalid_vm_configuration():
    with pytest.raises(ValidationError):
        EVM.configure(vm_configuration=[(-1, FrontierVM)])

    with pytest.raises(ValidationError):
        EVM.configure(vm_configuration=[
            (0, FrontierVM),
            (0, HomesteadVM),
            ]
        )
