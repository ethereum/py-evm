from eth_utils import decode_hex

from tests.core.fixtures import (  # noqa: F401
    shard_chain_without_block_validation,
)
from tests.core.helpers import (
    new_sharding_transaction,
)
from tests.core.vm.contract_fixture import (
    contract_bytecode,
    contract_address,
)


def test_sharding_transaction(shard_chain_without_block_validation):  # noqa: F811
    chain = shard_chain_without_block_validation
    deploy_tx = new_sharding_transaction(contract_address, b'', 0, b'', b'', contract_bytecode)

    vm = chain.get_vm()
    computation = vm.apply_transaction(deploy_tx)
    assert not computation.is_error

    # Transfer ether to recipient
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    tx_initiator = contract_address
    transfer_tx = new_sharding_transaction(tx_initiator, recipient, amount, b'', b'', b'')

    computation = vm.execute_transaction(transfer_tx)
    assert not computation.is_error
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(recipient) == amount
