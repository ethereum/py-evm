import rlp

from eth_utils import decode_hex

from evm import constants
from evm.vm.flavors.frontier.blocks import FrontierBlock

from tests.core.fixtures import (  # noqa: F401
    chain,
    chain_without_block_validation,
    valid_block_rlp,
)
from tests.core.helpers import new_transaction


def test_import_block_validation(chain):  # noqa: F811
    block = rlp.decode(valid_block_rlp, sedes=FrontierBlock, db=chain.db)
    imported_block = chain.import_block(block)
    assert len(imported_block.transactions) == 1
    tx = imported_block.transactions[0]
    assert tx.value == 10
    vm = chain.get_vm()
    with vm.state_db(read_only=True) as state_db:
        assert state_db.get_balance(
            decode_hex("095e7baea6a6c7c4c2dfeb977efac326af552d87")) == tx.value
        tx_gas = tx.gas_price * constants.GAS_TX
        assert state_db.get_balance(chain.funded_address) == (
            chain.funded_address_initial_balance - tx.value - tx_gas)


def test_import_block(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    vm = chain.get_vm()
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
    computation = vm.apply_transaction(tx)
    assert computation.error is None
    block = chain.import_block(vm.block)
    assert block.transactions == [tx]
    assert chain.get_block_by_hash(block.hash) == block
    assert chain.get_canonical_block_by_number(block.number) == block
