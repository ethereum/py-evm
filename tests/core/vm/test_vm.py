import pytest

from eth_utils import (
    decode_hex,
    ValidationError,
)

from eth import constants
from eth.chains.base import (
    MiningChain,
)
from eth.chains.mainnet import MAINNET_VMS
from eth.tools.builder.chain import api
from eth.tools.factories.transaction import (
    new_transaction
)


@pytest.fixture(params=MAINNET_VMS)
def pow_consensus_chain(request):
    return api.build(
        MiningChain,
        api.fork_at(request.param, 0),
        api.genesis(),
    )


@pytest.fixture(params=MAINNET_VMS)
def noproof_consensus_chain(request):
    return api.build(
        MiningChain,
        api.fork_at(request.param, 0),
        api.disable_pow_check(),
        api.genesis(),
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
    # Create to "structurally valid" blocks that are not backed by PoW
    block1 = noproof_consensus_chain.mine_block()
    block2 = noproof_consensus_chain.mine_block()

    vm = pow_consensus_chain.get_vm(block2.header)

    # The `validate_header` check is expected to succeed as it does not perform seal validation
    vm.validate_header(block2.header, block1.header)

    with pytest.raises(ValidationError, match="mix hash mismatch"):
        vm.validate_seal(block2.header)


def test_validate_header_fails_on_invalid_parent(noproof_consensus_chain):
    block1 = noproof_consensus_chain.mine_block()
    noproof_consensus_chain.mine_block()
    block3 = noproof_consensus_chain.mine_block()

    vm = noproof_consensus_chain.get_vm(block3.header)

    with pytest.raises(ValidationError, match="Blocks must be numbered consecutively"):
        vm.validate_header(block3.header, block1.header)
