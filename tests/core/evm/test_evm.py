import pytest

from evm import constants
from evm import EVM

from evm.exceptions import EVMNotFound
from evm.vm.flavors.frontier import FrontierVM
from evm.vm.flavors.homestead import HomesteadVM


def test_get_vm_class_for_block_number():
    evm = EVM.configure(
        vm_configuration=(
            (0, FrontierVM),
            (constants.HOMESTEAD_MAINNET_BLOCK, HomesteadVM),
        ),
    )
    assert evm.get_vm_class_for_block_number(0) == FrontierVM
    assert evm.get_vm_class_for_block_number(constants.HOMESTEAD_MAINNET_BLOCK - 1) == FrontierVM
    assert evm.get_vm_class_for_block_number(constants.HOMESTEAD_MAINNET_BLOCK) == HomesteadVM
    assert evm.get_vm_class_for_block_number(constants.HOMESTEAD_MAINNET_BLOCK + 1) == HomesteadVM

    unconfigured_evm = EVM.configure(vm_configuration=())
    with pytest.raises(EVMNotFound):
        unconfigured_evm.get_vm_class_for_block_number(0)
