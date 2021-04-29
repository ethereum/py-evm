from eth.vm.forks.berlin.constants import (
    ACCESS_LIST_ADDRESS_COST_EIP_2930,
    ACCESS_LIST_STORAGE_KEY_COST_EIP_2930,
)

# EIP 1559
BASE_GAS_FEE_TRANSACTION_TYPE = 2
BASE_GAS_FEE_ADDRESS_COST = ACCESS_LIST_ADDRESS_COST_EIP_2930
BASE_GAS_FEE_STORAGE_KEY_COST = ACCESS_LIST_STORAGE_KEY_COST_EIP_2930

BASE_FEE_MAX_CHANGE_DENOMINATOR = 8
ELASTICITY_MULTIPLIER = 2
