from eth_utils import (
    ValidationError,
)
import pytest

from eth._utils.address import (
    force_bytes_to_address,
)
from eth.chains.base import (
    MiningChain,
)
from eth.constants import (
    GAS_TX,
)
from eth.tools.factories.transaction import (
    new_dynamic_fee_transaction,
)
from eth.vm.forks import (
    LondonVM,
)


@pytest.fixture
def london_plus_miner(chain_without_block_validation):
    if not isinstance(chain_without_block_validation, MiningChain):
        pytest.skip("This test is only meant to run with mining capability")
        return

    valid_vms = (LondonVM,)
    vm = chain_without_block_validation.get_vm()
    if isinstance(vm, valid_vms):
        return chain_without_block_validation
    else:
        pytest.skip("This test is not meant to run on pre-London VMs")


ADDRESS_A = force_bytes_to_address(b"\x10\x10")


def test_transaction_cost_valid(
    london_plus_miner, funded_address, funded_address_private_key
):
    chain = london_plus_miner
    vm = chain.get_vm()
    base_fee_per_gas = vm.get_header().base_fee_per_gas
    # Make sure we're testing an interesting case
    assert base_fee_per_gas > 0

    account_balance = vm.state.get_balance(funded_address)

    tx = new_dynamic_fee_transaction(
        vm,
        from_=funded_address,
        to=ADDRESS_A,
        private_key=funded_address_private_key,
        gas=GAS_TX,
        amount=account_balance - base_fee_per_gas * GAS_TX,
        max_priority_fee_per_gas=1,
        max_fee_per_gas=base_fee_per_gas,
    )

    # sanity check
    assert vm.get_header().gas_used == 0

    # There should be no validation failure when applying the transaction
    chain.apply_transaction(tx)

    # sanity check: make sure the transaction actually got applied
    assert chain.get_vm().get_header().gas_used > 0


def test_transaction_cost_invalid(
    london_plus_miner, funded_address, funded_address_private_key
):
    chain = london_plus_miner
    vm = chain.get_vm()
    base_fee_per_gas = vm.get_header().base_fee_per_gas
    # Make sure we're testing an interesting case
    assert base_fee_per_gas > 0

    account_balance = vm.state.get_balance(funded_address)

    tx = new_dynamic_fee_transaction(
        vm,
        from_=funded_address,
        to=ADDRESS_A,
        private_key=funded_address_private_key,
        gas=GAS_TX,
        amount=account_balance - base_fee_per_gas * GAS_TX + 1,
        max_priority_fee_per_gas=1,
        max_fee_per_gas=base_fee_per_gas,
    )

    # sanity check
    assert vm.get_header().gas_used == 0

    # The *validation* step should catch that the sender does not have enough funds. If
    # validation misses the problem, then we might see an InsufficientFunds, because the
    # VM will think the transaction is fine, then attempt to execute it,
    # then then run out of funds.
    with pytest.raises(ValidationError):
        chain.apply_transaction(tx)

    # sanity check: make sure the transaction does not get applied
    assert chain.get_vm().get_header().gas_used == 0
