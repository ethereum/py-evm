import copy
import os

import json

from eth_utils import (
    int_to_big_endian,
    decode_hex,
)

from evm.db.state import (
    ShardingAccountStateDB,
)
from evm.exceptions import (
    IncorrectContractCreationAddress,
    ContractCreationCollision,
)
from evm.utils.address import generate_CREATE2_contract_address
from evm.utils.padding import pad32
from evm.utils.state_access_restriction import (
    to_prefix_list_form,
)
from evm.vm.witness_package import (
    WitnessPackage,
)

from tests.core.helpers import (
    new_sharding_transaction,
)


DIR = os.path.dirname(__file__)


def deploy_simple_contract(
        vm,
        tx_initiator,
        code,
        access_list=None):

    tx = new_sharding_transaction(
        tx_initiator=tx_initiator,
        data_destination=b'',
        data_value=0,
        data_msgdata=b'',
        data_vrs=b'',
        code=code,
        access_list=access_list,
    )
    computation, _ = vm.apply_transaction(tx)
    return vm, computation, tx


def test_sharding_apply_transaction(unvalidated_shard_chain):  # noqa: F811
    chain = unvalidated_shard_chain

    CREATE2_contracts = json.load(
        open(os.path.join(DIR, '../contract_fixtures/CREATE2_contracts.json'))
    )
    simple_transfer_contract = CREATE2_contracts["simple_transfer_contract"]
    CREATE2_contract = CREATE2_contracts["CREATE2_contract"]
    simple_factory_contract_bytecode = CREATE2_contracts["simple_factory_contract"]["bytecode"]

    # First test: simple ether transfer contract
    vm = chain.get_vm()
    vm, computation, tx = deploy_simple_contract(
        vm,
        decode_hex(simple_transfer_contract['address']),
        simple_transfer_contract['bytecode'],
    )

    assert computation.is_success
    gas_used = vm.block.header.gas_used
    assert gas_used > tx.intrinsic_gas
    last_gas_used = gas_used

    # Transfer ether to recipient
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    tx_initiator = decode_hex(simple_transfer_contract['address'])
    transfer_tx = new_sharding_transaction(tx_initiator, recipient, amount, b'', b'')

    computation, _ = vm.apply_transaction(transfer_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > transfer_tx.intrinsic_gas
    last_gas_used = vm.block.header.gas_used
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(recipient) == amount

    # Second test: contract that deploy new contract with CREATE2
    vm, computation, tx = deploy_simple_contract(
        vm,
        decode_hex(CREATE2_contract['address']),
        CREATE2_contract['bytecode'],
    )

    assert computation.is_success
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > tx.intrinsic_gas
    last_gas_used = vm.block.header.gas_used

    # Invoke the contract to deploy new contract
    tx_initiator = decode_hex(CREATE2_contract['address'])
    newly_deployed_contract_address = generate_CREATE2_contract_address(
        int_to_big_endian(0),
        decode_hex(simple_factory_contract_bytecode)
    )
    invoke_tx = new_sharding_transaction(
        tx_initiator,
        b'',
        0,
        b'',
        b'',
        access_list=[[tx_initiator, pad32(b'')], [newly_deployed_contract_address]]
    )

    computation, _ = vm.apply_transaction(invoke_tx)
    assert not computation.is_error
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > invoke_tx.intrinsic_gas
    with vm.state.state_db(read_only=True) as state_db:
        newly_deployed_contract_address = generate_CREATE2_contract_address(
            int_to_big_endian(0),
            decode_hex(simple_factory_contract_bytecode)
        )
        assert state_db.get_code(newly_deployed_contract_address) == b'\xbe\xef'
        assert state_db.get_storage(decode_hex(CREATE2_contract['address']), 0) == 1


def test_CREATE2_deploy_contract_edge_cases(unvalidated_shard_chain):  # noqa: F811
    CREATE2_contracts = json.load(
        open(os.path.join(DIR, '../contract_fixtures/CREATE2_contracts.json'))
    )
    simple_transfer_contract = CREATE2_contracts["simple_transfer_contract"]

    # First case: computed contract address not the same as provided in `transaction.to`
    chain = unvalidated_shard_chain
    code = "0xf3"
    computed_address = generate_CREATE2_contract_address(b"", decode_hex(code))

    vm = chain.get_vm()
    vm, computation, tx = deploy_simple_contract(
        vm,
        decode_hex(simple_transfer_contract['address']),
        code,
        access_list=[[decode_hex(simple_transfer_contract['address'])], [computed_address]],
    )

    assert isinstance(computation._error, IncorrectContractCreationAddress)
    gas_used = vm.block.header.gas_used
    assert gas_used > tx.intrinsic_gas
    last_gas_used = gas_used

    # Next, complete deploying the contract
    vm, computation, tx = deploy_simple_contract(
        vm,
        decode_hex(simple_transfer_contract['address']),
        simple_transfer_contract['bytecode'],
        access_list=[[decode_hex(simple_transfer_contract['address'])], [computed_address]],
    )

    assert computation.is_success
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > tx.intrinsic_gas
    last_gas_used = gas_used

    # Second case: deploy to existing account
    second_failed_deploy_tx = tx
    computation, _ = vm.apply_transaction(second_failed_deploy_tx)
    assert isinstance(computation._error, ContractCreationCollision)
    gas_used = vm.block.header.gas_used - last_gas_used
    assert gas_used > second_failed_deploy_tx.intrinsic_gas


def test_build_block(unvalidated_shard_chain):  # noqa: F811
    CREATE2_contracts = json.load(
        open(os.path.join(DIR, '../contract_fixtures/CREATE2_contracts.json'))
    )
    simple_transfer_contract = CREATE2_contracts["simple_transfer_contract"]

    shard = unvalidated_shard_chain
    vm = shard.get_vm()

    vm, computation, tx = deploy_simple_contract(
        vm,
        decode_hex(simple_transfer_contract['address']),
        simple_transfer_contract['bytecode'],
    )
    assert computation.is_success

    # (1) Empty block.
    block = vm.mine_block()
    block0 = shard.import_block(block)
    initial_state_root = block0.header.state_root

    # (2) Use VM.apply_transaction to get the witness data
    chain1 = copy.deepcopy(shard)
    vm = chain1.get_vm()

    # The first transaction
    vm1 = shard.get_vm()

    tx_initiator = decode_hex(simple_transfer_contract['address'])
    recipient1 = decode_hex('0x1111111111111111111111111111111111111111')
    amount = 100
    access_list = [[tx_initiator], [recipient1]]
    tx1 = new_sharding_transaction(
        tx_initiator,
        recipient1,
        amount,
        b'',
        b'',
        access_list=access_list,
    )

    # Get the witness of tx1
    prefixes = to_prefix_list_form(access_list)
    transaction_witness1 = vm1.chaindb.get_witness_nodes(vm.state.state_root, prefixes)

    computation, _ = vm1.apply_transaction(tx1)
    assert computation.is_success

    with vm1.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(recipient1) == amount

    # The second transaction
    recipient2 = decode_hex('0x2222222222222222222222222222222222222222')
    access_list = [[tx_initiator], [recipient2]]
    tx2 = new_sharding_transaction(
        tx_initiator,
        recipient2,
        amount,
        b'',
        b'',
        access_list=access_list,
    )
    # Get the witness of tx2
    prefixes = to_prefix_list_form(access_list)
    transaction_witness2 = vm1.chaindb.get_witness_nodes(vm.state.state_root, prefixes)

    computation, _ = vm1.apply_transaction(tx2)
    assert computation.is_success

    # Create a block and import to chain
    coinbase = tx_initiator
    vm1.block.header.coinbase = coinbase
    # assert len(vm1.block.transactions) == 2
    block1 = chain1.import_block(vm1.block)

    # Check the block
    vm1 = chain1.get_vm()
    assert block1.header.coinbase == coinbase
    assert len(block1.transactions) == 2
    assert len(block1.get_receipts(vm1.chaindb)) == 2
    with vm1.state.state_db(read_only=True) as state_db1:
        assert state_db1.root_hash == block1.header.state_root

    # (3) Try to create a block by witnesses
    chain2 = copy.deepcopy(shard)
    vm2 = chain2.get_vm()
    transaction_packages = [
        (tx1, transaction_witness1),
        (tx2, transaction_witness2),
    ]
    prev_hashes = vm2.get_prev_hashes(
        last_block_hash=block0.hash,
        db=vm2.chaindb,
    )
    parent_header = block0.header
    account_state_class = ShardingAccountStateDB
    prefixes = to_prefix_list_form([[coinbase]])
    coinbase_witness = vm.chaindb.get_witness_nodes(
        vm2.state.state_root,
        prefixes,
    )
    # Create a witness package for building a block.
    witness_package = WitnessPackage(
        coinbase=coinbase,
        coinbase_witness=coinbase_witness,
        transaction_packages=transaction_packages,
    )
    # Create a block.
    block2, block2_witness = vm2.build_block(
        witness_package=witness_package,
        prev_hashes=prev_hashes,
        parent_header=parent_header,
        account_state_class=account_state_class,
    )

    # Check the block
    # assert len(block2.transactions) == 2
    assert block2.header.block_number == 2
    assert block2.header.coinbase == coinbase

    # Check if block2 == block1
    assert block2.hash == block1.hash

    # Check if the given parameters are changed
    assert block0.header.state_root == initial_state_root
    assert block0.header.block_number == 1
    for item in transaction_witness1:
        assert item in block2_witness

    # (4) Apply block with block witness
    chain3 = copy.deepcopy(shard)
    block3 = chain3.apply_block_with_witness(block2, block2_witness)

    # Check the block
    assert block3.hash == block1.hash
