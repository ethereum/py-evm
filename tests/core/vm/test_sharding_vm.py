from eth_utils import (
    int_to_big_endian,
    decode_hex,
)

from evm.utils.address import generate_CREATE2_contract_address

from tests.core.fixtures import (  # noqa: F401
    shard_chain_without_block_validation,
)
from tests.core.helpers import (
    new_sharding_transaction,
)
from tests.core.vm.contract_fixture import (
    simple_transfer_contract_bytecode,
    simple_transfer_contract_address,
    simple_contract_factory_bytecode,
    CREATE2_contract_bytecode,
    CREATE2_contract_address,
)


def test_sharding_apply_transaction(shard_chain_without_block_validation):  # noqa: F811
    chain = shard_chain_without_block_validation
    # First test: simple ether transfer contract
    first_deploy_tx = new_sharding_transaction(
        simple_transfer_contract_address,
        b'',
        0,
        b'',
        b'',
        simple_transfer_contract_bytecode
    )

    vm = chain.get_vm()
    computation = vm.apply_transaction(first_deploy_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used
    assert gas_used > first_deploy_tx.intrinsic_gas
    last_gas_used = gas_used

    # Transfer ether to recipient
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    tx_initiator = simple_transfer_contract_address
    transfer_tx = new_sharding_transaction(tx_initiator, recipient, amount, b'', b'', b'')

    computation = vm.apply_transaction(transfer_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > transfer_tx.intrinsic_gas
    last_gas_used = vm.block.header.gas_used
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(recipient) == amount

    # Second test: contract that deploy new contract with CREATE2
    second_deploy_tx = new_sharding_transaction(
        CREATE2_contract_address,
        b'',
        0,
        b'',
        b'',
        CREATE2_contract_bytecode
    )

    computation = vm.apply_transaction(second_deploy_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > second_deploy_tx.intrinsic_gas
    last_gas_used = vm.block.header.gas_used

    # Invoke the contract to deploy new contract
    tx_initiator = CREATE2_contract_address
    invoke_tx = new_sharding_transaction(tx_initiator, b'', 0, b'', b'', b'')

    computation = vm.apply_transaction(invoke_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > invoke_tx.intrinsic_gas
    with vm.state.state_db(read_only=True) as state_db:
        newly_deployed_contract_address = generate_CREATE2_contract_address(
            int_to_big_endian(0),
            simple_contract_factory_bytecode
        )
        assert state_db.get_code(newly_deployed_contract_address) == b'\xbe\xef'
        assert state_db.get_storage(CREATE2_contract_address, 0) == 1


def test_CREATE2_deploy_contract_edge_cases(shard_chain_without_block_validation):  # noqa: F811
    # First case: computed contract address not the same as provided in `transaction.to`
    chain = shard_chain_without_block_validation
    first_failed_deploy_tx = new_sharding_transaction(
        simple_transfer_contract_address,
        b'',
        0,
        b'',
        b'',
        '0xf3',
    )

    vm = chain.get_vm()
    computation = vm.apply_transaction(first_failed_deploy_tx)
    assert computation.is_error
    gas_used = vm.block.header.gas_used
    assert gas_used > first_failed_deploy_tx.intrinsic_gas
    last_gas_used = gas_used

    # Next, complete deploying the contract
    successful_deploy_tx = new_sharding_transaction(
        simple_transfer_contract_address,
        b'',
        0,
        b'',
        b'',
        simple_transfer_contract_bytecode
    )
    computation = vm.apply_transaction(successful_deploy_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > successful_deploy_tx.intrinsic_gas
    last_gas_used = gas_used

    # Second case: deploy to existing account
    second_failed_deploy_tx = successful_deploy_tx
    computation = vm.apply_transaction(second_failed_deploy_tx)
    assert computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > second_failed_deploy_tx.intrinsic_gas
