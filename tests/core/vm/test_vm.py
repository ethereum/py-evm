import pytest

import rlp
from eth_utils import (
    decode_hex,
    ValidationError,
)

from eth import constants
from eth.chains.base import (
    MiningChain,
)
from eth.chains.mainnet import MAINNET_VMS
from eth.exceptions import PyEVMError
from eth.tools.builder.chain import api
from eth.tools.factories.transaction import (
    new_transaction
)
from eth_typing import BlockNumber, Hash32
from eth._utils.headers import fill_header_params_from_parent


@pytest.fixture(params=MAINNET_VMS)
def vm_class(request):
    return request.param


@pytest.fixture
def pow_consensus_chain(vm_class):
    return api.build(
        MiningChain,
        api.fork_at(vm_class, 0),
        api.genesis(),
    )


@pytest.fixture
def noproof_consensus_chain(vm_class):
    # This will always have the same vm configuration as the POW chain
    return api.build(
        MiningChain,
        api.fork_at(vm_class, 0),
        api.disable_pow_check(),
        api.genesis(params=dict(gas_limit=100000)),
    )


@pytest.fixture
def chain(chain_without_block_validation):
    return chain_without_block_validation


def test_apply_transaction(
        chain,
        funded_address,
        funded_address_private_key,
        funded_address_initial_balance):
    vm = chain.get_vm()
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = funded_address
    tx = new_transaction(vm, from_, recipient, amount, funded_address_private_key)
    receipt, computation = vm.apply_transaction(vm.get_header(), tx)
    new_header = vm.add_receipt_to_header(vm.get_header(), receipt)

    assert not computation.is_error
    tx_gas = tx.gas_price * constants.GAS_TX
    state = vm.state
    assert state.get_balance(from_) == (
        funded_address_initial_balance - amount - tx_gas)
    assert state.get_balance(recipient) == amount

    assert new_header.gas_used == constants.GAS_TX


def test_block_serialization(chain):
    if not isinstance(chain, MiningChain):
        pytest.skip("Only test mining on a MiningChain")
        return

    block = chain.mine_block()
    rlp.encode(block)


def test_mine_block_issues_block_reward(chain):
    if not isinstance(chain, MiningChain):
        pytest.skip("Only test mining on a MiningChain")
        return

    block = chain.mine_block()
    vm = chain.get_vm()
    coinbase_balance = vm.state.get_balance(block.header.coinbase)
    assert coinbase_balance == vm.get_block_reward()


def test_import_block(chain, funded_address, funded_address_private_key):
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = funded_address
    tx = new_transaction(chain.get_vm(), from_, recipient, amount, funded_address_private_key)
    if isinstance(chain, MiningChain):
        # Can use the mining chain functionality to build transactions in-flight
        pending_header = chain.header
        new_block, _, computation = chain.apply_transaction(tx)
    else:
        # Have to manually build the block for the import_block test
        new_block, _, computations = chain.build_block_with_transactions([tx])
        computation = computations[0]

        # Generate the pending header to import the new block on
        pending_header = chain.create_header_from_parent(chain.get_canonical_head())

    assert not computation.is_error

    # import the built block
    validation_vm = chain.get_vm(pending_header)
    block, _ = validation_vm.import_block(new_block)
    assert block.transactions == (tx, )


def test_validate_header_succeeds_but_pow_fails(pow_consensus_chain, noproof_consensus_chain):
    # Create two "structurally valid" blocks that are not backed by PoW
    block1 = noproof_consensus_chain.mine_block()
    block2 = noproof_consensus_chain.mine_block()

    vm = pow_consensus_chain.get_vm(block2.header)

    # The `validate_header` check is expected to succeed as it does not perform seal validation
    vm.validate_header(block2.header, block1.header)

    with pytest.raises(ValidationError, match="mix hash mismatch"):
        vm.validate_seal(block2.header)


def test_validate_header_fails_on_invalid_parent(noproof_consensus_chain):
    block1 = noproof_consensus_chain.mine_block()
    block2 = noproof_consensus_chain.mine_block()

    vm = noproof_consensus_chain.get_vm(block2.header)

    with pytest.raises(ValidationError, match="Blocks must be numbered consecutively"):
        vm.validate_header(block2.header.copy(block_number=3), block1.header)


def test_validate_gas_limit_almost_too_low(noproof_consensus_chain):
    block1 = noproof_consensus_chain.mine_block()
    block2 = noproof_consensus_chain.mine_block()

    max_reduction = block1.header.gas_limit // constants.GAS_LIMIT_ADJUSTMENT_FACTOR - 1
    barely_valid_low_gas_limit = block1.header.gas_limit - max_reduction
    barely_valid_header = block2.header.copy(gas_limit=barely_valid_low_gas_limit)

    vm = noproof_consensus_chain.get_vm(block2.header)

    vm.validate_header(barely_valid_header, block1.header)


def test_validate_gas_limit_too_low(noproof_consensus_chain):
    block1 = noproof_consensus_chain.mine_block()
    block2 = noproof_consensus_chain.mine_block()

    exclusive_decrease_limit = block1.header.gas_limit // constants.GAS_LIMIT_ADJUSTMENT_FACTOR
    invalid_low_gas_limit = block1.header.gas_limit - exclusive_decrease_limit
    invalid_header = block2.header.copy(gas_limit=invalid_low_gas_limit)

    vm = noproof_consensus_chain.get_vm(block2.header)

    with pytest.raises(ValidationError, match="[Gg]as limit"):
        vm.validate_header(invalid_header, block1.header)


def test_validate_gas_limit_almost_too_high(noproof_consensus_chain):
    block1 = noproof_consensus_chain.mine_block()
    block2 = noproof_consensus_chain.mine_block()

    max_increase = block1.header.gas_limit // constants.GAS_LIMIT_ADJUSTMENT_FACTOR - 1
    barely_valid_high_gas_limit = block1.header.gas_limit + max_increase
    barely_valid_header = block2.header.copy(gas_limit=barely_valid_high_gas_limit)

    vm = noproof_consensus_chain.get_vm(block2.header)

    vm.validate_header(barely_valid_header, block1.header)


def test_validate_gas_limit_too_high(noproof_consensus_chain):
    block1 = noproof_consensus_chain.mine_block()
    block2 = noproof_consensus_chain.mine_block()

    exclusive_increase_limit = block1.header.gas_limit // constants.GAS_LIMIT_ADJUSTMENT_FACTOR
    invalid_high_gas_limit = block1.header.gas_limit + exclusive_increase_limit
    invalid_header = block2.header.copy(gas_limit=invalid_high_gas_limit)

    vm = noproof_consensus_chain.get_vm(block2.header)

    with pytest.raises(ValidationError, match="[Gg]as limit"):
        vm.validate_header(invalid_header, block1.header)


@pytest.mark.parametrize(
    "custom_header_params,null_parent",
    (
        ({
            'gas_limit': 1,
            'difficulty': 10,
            'timestamp': 100,
            'block_number': 1000
        }, True),
        ({
            'gas_limit': 1,
            'difficulty': 10,
            'timestamp': 100,
        }, False),
        ({
            'gas_limit': 1,
            'difficulty': 10,
            'timestamp': 100,
            'block_number': 1000,
        }, False)
    )
)
def test_fill_header_params_from_parent(custom_header_params, null_parent,
                                        noproof_consensus_chain):
    # Handle cases which want to specify a null parent.
    block = noproof_consensus_chain.mine_block()
    header = block.header if null_parent is False else None

    # Cannot specify block number and a parent.
    if 'block_number' in custom_header_params and header is not None:
        with pytest.raises(PyEVMError, match="block_number cannot be configured if a parent header exists."):
            new_header_params = fill_header_params_from_parent(header, **custom_header_params)
        return
    new_header_params = fill_header_params_from_parent(header, **custom_header_params)

    # Compare fields which are copied no matter what.
    trivial_fields = ['gas_limit', 'difficulty', 'timestamp']
    for field in trivial_fields:
        assert new_header_params[field] == custom_header_params[field]

    # Check `block_number` and `parent_hash` cases.
    if 'block_number' in custom_header_params:
        assert new_header_params['block_number'] == custom_header_params['block_number']
        assert new_header_params['parent_hash'] == constants.GENESIS_PARENT_HASH
    elif header is None:
        assert new_header_params['block_number'] == constants.GENESIS_BLOCK_NUMBER
        assert new_header_params['parent_hash'] == constants.GENESIS_PARENT_HASH
    else:
        assert new_header_params['block_number'] == BlockNumber(header['block_number'] + 1)
        assert new_header_params['parent_hash'] == header.hash
