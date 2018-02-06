from eth_utils import (
    decode_hex,
)

from tests.core.helpers import (
    new_sharding_transaction,
)
from tests.core.vm.contract_fixture import (
    PAYGAS_contract_bytecode,
    PAYGAS_contract_address,
)


def test_trigger_PAYGAS(unvalidated_shard_chain):  # noqa: F811
    chain = unvalidated_shard_chain
    deploy_tx = new_sharding_transaction(
        tx_initiator=PAYGAS_contract_address,
        data_destination=b'',
        data_value=0,
        data_msgdata=b'',
        data_vrs=b'',
        code=PAYGAS_contract_bytecode,
    )

    vm = chain.get_vm()
    computation, _ = vm.apply_transaction(deploy_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used
    assert gas_used > deploy_tx.intrinsic_gas
    last_gas_used = gas_used

    # Trigger the contract
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    tx_initiator = PAYGAS_contract_address
    gas_price = bytes([33])
    vrs = 64 * b'\xAA' + b'\x01'
    trigger_tx = new_sharding_transaction(tx_initiator, recipient, amount, gas_price, vrs, b'')

    computation, _ = vm.apply_transaction(trigger_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > trigger_tx.intrinsic_gas
    last_gas_used = vm.block.header.gas_used
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(recipient) == amount
