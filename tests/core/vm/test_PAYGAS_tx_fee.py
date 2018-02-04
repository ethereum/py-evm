from eth_utils import (
    decode_hex,
)

from tests.core.helpers import (
    new_sharding_transaction,
)
from tests.core.vm.contract_fixture import (
    PAYGAS_contract_normal,
    simple_forwarder_contract,
    PAYGAS_contract_triggered_twice,
)


def test_trigger_PAYGAS(unvalidated_shard_chain):  # noqa: F811
    chain = unvalidated_shard_chain
    vm = chain.get_vm()

    deploy_tx = new_sharding_transaction(
        tx_initiator=PAYGAS_contract_normal['address'],
        data_destination=b'',
        data_value=0,
        data_msgdata=b'',
        data_vrs=b'',
        code=PAYGAS_contract_normal['bytecode'],
    )
    computation, _ = vm.apply_transaction(deploy_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used
    assert gas_used > deploy_tx.intrinsic_gas
    last_gas_used = gas_used

    # Trigger the contract
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 0
    tx_initiator = PAYGAS_contract_normal['address']
    gas_price = 33
    vrs = 64 * b'\xAA' + b'\x01'
    trigger_tx = new_sharding_transaction(
        tx_initiator,
        recipient,
        amount,
        bytes([gas_price]),
        vrs,
        b''
    )

    with vm.state.state_db(read_only=True) as state_db:
        balance_before_trigger = state_db.get_balance(simple_forwarder_contract['address'])
    computation, _ = vm.apply_transaction(trigger_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > trigger_tx.intrinsic_gas
    last_gas_used = vm.block.header.gas_used
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(tx_initiator) == balance_before_trigger - gas_used * gas_price
        assert state_db.get_balance(recipient) == amount


def test_PAYGAS_edge_cases(shard_chain_without_block_validation):  # noqa: F811
    # Case 1: PAYGAS not triggered
    chain = shard_chain_without_block_validation
    vm = chain.get_vm()

    forwarder_addr = simple_forwarder_contract['address']
    forwarder_contract_deploy_tx = new_sharding_transaction(
        tx_initiator=forwarder_addr,
        data_destination=b'',
        data_value=0,
        data_msgdata=b'',
        data_vrs=b'',
        code=simple_forwarder_contract['bytecode'],
    )
    computation, _ = vm.apply_transaction(forwarder_contract_deploy_tx)
    assert not computation.is_error

    # Trigger the forwarder contract which does not have PAYGAS opcode
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 0
    tx_initiator = forwarder_addr
    gas_price = bytes([0])
    vrs = 64 * b'\xAA' + b'\x01'
    trigger_tx = new_sharding_transaction(tx_initiator, recipient, amount, gas_price, vrs, b'')

    with vm.state.state_db(read_only=True) as state_db:
        balance_before_trigger = state_db.get_balance(forwarder_addr)
    computation, _ = vm.apply_transaction(trigger_tx)
    assert not computation.is_error
    with vm.state.state_db(read_only=True) as state_db:
        # Check that balance of the contract is the same
        assert balance_before_trigger == state_db.get_balance(forwarder_addr)
    
    # Case 2: PAYGAS triggered with 0 gas price
    PAYGAS_contract_addr = PAYGAS_contract_normal['address']
    normal_PAYGAS_contract_deploy_tx = new_sharding_transaction(
        tx_initiator=PAYGAS_contract_addr,
        data_destination=b'',
        data_value=0,
        data_msgdata=b'',
        data_vrs=b'',
        code=PAYGAS_contract_normal['bytecode'],
    )
    computation, _ = vm.apply_transaction(normal_PAYGAS_contract_deploy_tx)
    assert not computation.is_error

    # Trigger the PAYGAS contract with gas price set to 0
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    tx_initiator = PAYGAS_contract_addr
    gas_price = bytes([0])
    vrs = 64 * b'\xAA' + b'\x01'
    trigger_tx = new_sharding_transaction(tx_initiator, recipient, amount, gas_price, vrs, b'')

    with vm.state.state_db(read_only=True) as state_db:
        balance_before_trigger = state_db.get_balance(PAYGAS_contract_addr)
    computation, _ = vm.apply_transaction(trigger_tx)
    assert not computation.is_error
    with vm.state.state_db(read_only=True) as state_db:
        # Check that balance of the contract is the same except the amount transfered
        assert balance_before_trigger == state_db.get_balance(PAYGAS_contract_addr) + amount
    
    # Case 3: PAYGAS is not triggered in a top level call
    # Use the forwarder contract in case 1 to make the call to PAYGAS contract in case 2
    # Order: forwarder -> PAYGAS contract -> recipient
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    tx_initiator = forwarder_addr
    vrs = 64 * b'\xAA' + b'\x01'
    access_list = [[tx_initiator], [recipient], [PAYGAS_contract_addr]]
    trigger_tx = new_sharding_transaction(
        tx_initiator,
        PAYGAS_contract_addr,
        amount,
        recipient,
        vrs,
        b'',
        access_list=access_list
    )

    with vm.state.state_db(read_only=True) as state_db:
        PAYGAS_balance_before_trigger = state_db.get_balance(PAYGAS_contract_addr)
        forwarder_balance_before_trigger = state_db.get_balance(forwarder_addr)
        recipient_balance_before_trigger = state_db.get_balance(recipient)
    computation, _ = vm.apply_transaction(trigger_tx)
    assert not computation.is_error
    with vm.state.state_db(read_only=True) as state_db:
        # Check that balance of these accounts are the same except the amount transfered
        assert PAYGAS_balance_before_trigger == state_db.get_balance(PAYGAS_contract_addr)
        assert forwarder_balance_before_trigger == state_db.get_balance(forwarder_addr) + amount
        assert state_db.get_balance(recipient) == recipient_balance_before_trigger + amount

    # Case 4: PAYGAS triggered twice
    PAYGAS_triggered_twice_addr = PAYGAS_contract_triggered_twice['address']
    PAYGAS_triggered_twice_deploy_tx = new_sharding_transaction(
        tx_initiator=PAYGAS_triggered_twice_addr,
        data_destination=b'',
        data_value=0,
        data_msgdata=b'',
        data_vrs=b'',
        code=PAYGAS_contract_triggered_twice['bytecode'],
    )
    computation, _ = vm.apply_transaction(PAYGAS_triggered_twice_deploy_tx)
    assert not computation.is_error

    # Trigger the PAYGAS contract which will trigger PAYGAS twice
    # First time with gas_price specified in transaction data
    # Second time with 10*gas_price
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    tx_initiator = PAYGAS_triggered_twice_addr
    gas_price = 33
    vrs = 64 * b'\xAA' + b'\x01'
    trigger_tx = new_sharding_transaction(
        tx_initiator,
        recipient,
        amount,
        bytes([gas_price]),
        vrs,
        b''
    )

    last_gas_used = vm.block.header.gas_used
    with vm.state.state_db(read_only=True) as state_db:
        balance_before_trigger = state_db.get_balance(PAYGAS_triggered_twice_addr)
        recipient_balance_before_trigger = state_db.get_balance(recipient)
    computation, _ = vm.apply_transaction(trigger_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    with vm.state.state_db(read_only=True) as state_db:
        # Check that PAYGAS account is charged with normal gas_price instead of 10*gas_price
        tx_fee = gas_used * gas_price
        assert balance_before_trigger == state_db.get_balance(PAYGAS_triggered_twice_addr) + tx_fee + amount
        assert state_db.get_balance(recipient) == recipient_balance_before_trigger + amount
