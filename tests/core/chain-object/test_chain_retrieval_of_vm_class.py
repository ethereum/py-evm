import pytest

from evm.db import (
    get_db_backend,
)


from evm import constants
from evm import Chain

from evm.exceptions import (
    ValidationError,
    VMNotFound,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.vm.flavors.frontier import FrontierVM
from evm.vm.flavors.homestead import HomesteadVM


def test_get_vm_class_for_block_number():
    chain_class = Chain.configure(
        vm_configuration=(
            (constants.GENESIS_BLOCK_NUMBER, FrontierVM),
            (constants.HOMESTEAD_MAINNET_BLOCK, HomesteadVM),
        ),
    )
    chain = chain_class(get_db_backend(), BlockHeader(1, 0, 100))
    assert chain.get_vm_class_for_block_number(
        constants.GENESIS_BLOCK_NUMBER,) == FrontierVM
    assert chain.get_vm_class_for_block_number(
        constants.HOMESTEAD_MAINNET_BLOCK - 1) == FrontierVM
    assert chain.get_vm_class_for_block_number(
        constants.HOMESTEAD_MAINNET_BLOCK) == HomesteadVM
    assert chain.get_vm_class_for_block_number(
        constants.HOMESTEAD_MAINNET_BLOCK + 1) == HomesteadVM


def test_invalid_if_no_vm_configuration():
    chain_class = Chain.configure(vm_configuration=())
    with pytest.raises(ValueError):
        chain_class(get_db_backend(), BlockHeader(1, 0, 100))


def test_vm_not_found_if_no_matching_block_number():
    chain_class = Chain.configure(vm_configuration=(
        (10, FrontierVM),
    ))
    chain = chain_class(get_db_backend(), BlockHeader(1, 0, 100))
    with pytest.raises(VMNotFound):
        chain.get_vm_class_for_block_number(9)


def test_configure_invalid_block_number_in_vm_configuration():
    with pytest.raises(ValidationError):
        Chain.configure(vm_configuration=[(-1, FrontierVM)])


def test_configure_duplicate_block_numbers_in_vm_configuration():
    with pytest.raises(ValidationError):
        Chain.configure(vm_configuration=[
                (0, FrontierVM),
                (0, HomesteadVM),
            ]
        )
