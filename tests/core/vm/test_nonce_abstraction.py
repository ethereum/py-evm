import os
import json

from eth_utils import (
    decode_hex,
)

from evm.utils.padding import pad32

from tests.core.helpers import (
    new_sharding_transaction,
)


DIR = os.path.dirname(__file__)
nonce_tracking_contracts = json.load(
    open(os.path.join(DIR, '../contract_fixtures/nonce_tracking_contracts.json'))
)


def test_contract_with_nonce_tracking(unvalidated_shard_chain):  # noqa: F811
    chain = unvalidated_shard_chain
    vm = chain.get_vm()

    nonce_tracking_contract = nonce_tracking_contracts["nonce_tracking_contract"]
    nonce_tracking_contract_address = decode_hex(nonce_tracking_contract['address'])
    deploy_tx = new_sharding_transaction(
        tx_initiator=nonce_tracking_contract_address,
        data_destination=b'',
        data_value=0,
        data_msgdata=b'',
        data_vrs=b'',
        code=nonce_tracking_contract['bytecode'],
    )
    computation, _ = vm.apply_transaction(deploy_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used
    assert gas_used > deploy_tx.intrinsic_gas
    last_gas_used = gas_used

    # Trigger the contract with correct nonce
    recipient = b''
    nonce = 0
    tx_initiator = nonce_tracking_contract_address
    gas_price = 33
    vrs = 64 * b'\xAA' + b'\x01'
    access_list = [[tx_initiator, pad32(b'\x00')]]
    trigger_tx = new_sharding_transaction(
        tx_initiator,
        recipient,
        nonce,
        bytes([gas_price]),
        vrs,
        b'',
        access_list=access_list,
    )

    with vm.state.state_db(read_only=True) as state_db:
        balance_before_trigger = state_db.get_balance(nonce_tracking_contract_address)
    computation, _ = vm.apply_transaction(trigger_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > trigger_tx.intrinsic_gas
    last_gas_used = vm.block.header.gas_used
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(tx_initiator) == balance_before_trigger - gas_used * gas_price
        # Check that nonce is incremented
        assert state_db.get_storage(tx_initiator, 0) == 1

    # Replay the same transaction
    with vm.state.state_db(read_only=True) as state_db:
        balance_before_trigger = state_db.get_balance(nonce_tracking_contract_address)
    computation, _ = vm.apply_transaction(trigger_tx)
    assert computation.is_error
    with vm.state.state_db(read_only=True) as state_db:
        # Check that no fee is charged since nonce given is incorrect
        assert state_db.get_balance(tx_initiator) == balance_before_trigger
        # Check that nonce is not incremented
        assert state_db.get_storage(tx_initiator, 0) == 1


def test_contract_with_no_nonce_tracking(unvalidated_shard_chain):  # noqa: F811
    chain = unvalidated_shard_chain
    vm = chain.get_vm()

    no_nonce_tracking_contract = nonce_tracking_contracts["no_nonce_tracking_contract"]
    no_nonce_tracking_contract_address = decode_hex(no_nonce_tracking_contract['address'])
    deploy_tx = new_sharding_transaction(
        tx_initiator=no_nonce_tracking_contract_address,
        data_destination=b'',
        data_value=0,
        data_msgdata=b'',
        data_vrs=b'',
        code=no_nonce_tracking_contract['bytecode'],
    )
    computation, _ = vm.apply_transaction(deploy_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used
    assert gas_used > deploy_tx.intrinsic_gas
    last_gas_used = gas_used

    # Trigger the contract
    recipient = b''
    nonce = 0
    tx_initiator = no_nonce_tracking_contract_address
    gas_price = 10
    vrs = 64 * b'\xAA' + b'\x01'
    access_list = [[tx_initiator, pad32(b'\x00')]]
    trigger_tx = new_sharding_transaction(
        tx_initiator,
        recipient,
        nonce,
        bytes([gas_price]),
        vrs,
        b'',
        access_list=access_list,
    )

    with vm.state.state_db(read_only=True) as state_db:
        balance_before_trigger = state_db.get_balance(no_nonce_tracking_contract_address)
    computation, _ = vm.apply_transaction(trigger_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > trigger_tx.intrinsic_gas
    last_gas_used = vm.block.header.gas_used
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(tx_initiator) == balance_before_trigger - gas_used * gas_price

    # Replay the same transaciton
    with vm.state.state_db(read_only=True) as state_db:
        balance_before_trigger = state_db.get_balance(no_nonce_tracking_contract_address)
    computation, _ = vm.apply_transaction(trigger_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > trigger_tx.intrinsic_gas
    last_gas_used = vm.block.header.gas_used
    with vm.state.state_db(read_only=True) as state_db:
        # Check that fee is charged since there's no replay protection
        assert state_db.get_balance(tx_initiator) == balance_before_trigger - gas_used * gas_price
