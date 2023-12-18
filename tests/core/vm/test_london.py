from eth_typing import (
    Address,
)
from eth_utils import (
    decode_hex,
)
import pytest

from eth import (
    constants,
)
from eth.chains.base import (
    MiningChain,
)
from eth.chains.mainnet import (
    MINING_MAINNET_VMS,
)
from eth.consensus.noproof import (
    NoProofConsensus,
)
from eth.exceptions import (
    InvalidInstruction,
)
from eth.tools.factories.transaction import (
    new_dynamic_fee_transaction,
    new_transaction,
)
from eth.vm.forks import (
    BerlinVM,
)

FOUR_TXN_GAS_LIMIT = 21000 * 4

EIP_3541_CREATE_AND_CREATE2_REVERT_TEST_CASES = (
    # negative test cases from https://eips.ethereum.org/EIPS/eip-3541#test-cases
    # CREATE opcode tests:
    (
        decode_hex("0x6000356000523660006000f0151560165760006000fd5b"),
        decode_hex("0x60ef60005360016000f3"),
    ),
    (
        decode_hex("0x6000356000523660006000f0151560165760006000fd5b"),
        decode_hex("0x60ef60005360026000f3"),
    ),
    (
        decode_hex("0x6000356000523660006000f0151560165760006000fd5b"),
        decode_hex("0x60ef60005360036000f3"),
    ),
    (
        decode_hex("0x6000356000523660006000f0151560165760006000fd5b"),
        decode_hex("0x60ef60005360206000f3"),
    ),
    # CREATE2 opcode tests:
    (
        decode_hex("0x60003560005260003660006000f5151560185760006000fd5b"),
        decode_hex("0x60ef60005360016000f3"),
    ),
    (
        decode_hex("0x60003560005260003660006000f5151560185760006000fd5b"),
        decode_hex("0x60ef60005360026000f3"),
    ),
    (
        decode_hex("0x60003560005260003660006000f5151560185760006000fd5b"),
        decode_hex("0x60ef60005360036000f3"),
    ),
    (
        decode_hex("0x60003560005260003660006000f5151560185760006000fd5b"),
        decode_hex("0x60ef60005360206000f3"),
    ),
)


def _configure_mining_chain(name, genesis_vm, vm_under_test):
    return MiningChain.configure(
        __name__=name,
        vm_configuration=(
            (
                constants.GENESIS_BLOCK_NUMBER,
                genesis_vm.configure(consensus_class=NoProofConsensus),
            ),
            (
                constants.GENESIS_BLOCK_NUMBER + 1,
                vm_under_test.configure(consensus_class=NoProofConsensus),
            ),
        ),
        chain_id=1337,
    )


# Mining VMs starting at London
@pytest.fixture(params=MINING_MAINNET_VMS[9:])
def london_plus_miner(request, base_db, genesis_state):
    vm_under_test = request.param

    klass = _configure_mining_chain("LondonAt1", BerlinVM, vm_under_test)
    header_fields = dict(
        difficulty=1,
        gas_limit=21000 * 2,  # block limit is hit with two transactions
    )
    # On the first London+ block, it will double the block limit so that it
    #   can precisely hold 4 base transactions.
    return klass.from_genesis(base_db, header_fields, genesis_state)


# Mining VMs up to, but not including, London
@pytest.fixture(params=MINING_MAINNET_VMS[0:9])
def pre_london_miner(request, base_db, genesis_state):
    vm_under_test = request.param

    klass = _configure_mining_chain(
        "EndsBeforeLondon", MINING_MAINNET_VMS[0], vm_under_test
    )
    header_fields = dict(
        difficulty=1,
        gas_limit=100000,  # arbitrary, just enough for testing
    )
    return klass.from_genesis(base_db, header_fields, genesis_state)


@pytest.mark.parametrize(
    "num_txns, expected_base_fee",
    (
        (0, 875000000),
        (1, 937500000),
        # base fee should stay stable at 1 gwei when block is exactly half full
        (2, 1000000000),
        (3, 1062500000),
        (4, 1125000000),
    ),
)
def test_base_fee_evolution(
    london_plus_miner,
    funded_address,
    funded_address_private_key,
    num_txns,
    expected_base_fee,
):
    chain = london_plus_miner
    assert chain.header.gas_limit == FOUR_TXN_GAS_LIMIT

    vm = chain.get_vm()
    txns = [
        new_transaction(
            vm,
            funded_address,
            b"\x00" * 20,
            private_key=funded_address_private_key,
            gas=21000,
            nonce=nonce,
        )
        for nonce in range(num_txns)
    ]
    block_import, _, _ = chain.mine_all(txns, gas_limit=FOUR_TXN_GAS_LIMIT)
    mined_header = block_import.imported_block.header
    assert mined_header.gas_limit == FOUR_TXN_GAS_LIMIT
    assert mined_header.gas_used == 21000 * num_txns
    assert mined_header.base_fee_per_gas == 10**9  # Initialize at 1 gwei

    block_import, _, _ = chain.mine_all([], gas_limit=FOUR_TXN_GAS_LIMIT)
    mined_header = block_import.imported_block.header
    assert mined_header.gas_limit == FOUR_TXN_GAS_LIMIT
    assert mined_header.gas_used == 0
    # Check that the base fee evolved correctly,
    # depending on how much gas was used in the parent
    assert mined_header.base_fee_per_gas == expected_base_fee


@pytest.mark.parametrize("code, data", EIP_3541_CREATE_AND_CREATE2_REVERT_TEST_CASES)
def test_revert_on_reserved_0xEF_byte_for_CREATE_and_CREATE2_post_london(
    london_plus_miner,
    funded_address,
    code,
    data,
):
    chain = london_plus_miner
    vm = chain.get_vm()

    # test positive case from https://eips.ethereum.org/EIPS/eip-3541#test-cases
    successful_create_computation = vm.execute_bytecode(
        origin=funded_address,
        to=funded_address,
        sender=funded_address,
        value=0,
        code=code,
        data=decode_hex("0x60fe60005360016000f3"),
        gas=400000,
        gas_price=1,
    )

    assert successful_create_computation.is_success
    # assert only the appropriate gas is consumed, not all the gas.
    # This falls within a range
    assert 32261 <= successful_create_computation.get_gas_used() <= 32270

    # test parameterized negative cases
    revert_create_computation = vm.execute_bytecode(
        origin=funded_address,
        to=funded_address,
        sender=funded_address,
        value=0,
        code=code,
        data=data,
        gas=40000,
        gas_price=1,
    )

    assert revert_create_computation.is_error
    assert (
        35000 < revert_create_computation.get_gas_used() < 40000
    )  # assert gas is still consumed
    assert revert_create_computation.get_gas_refund() == 0


@pytest.mark.parametrize(
    "data",
    (
        # negative test cases from https://eips.ethereum.org/EIPS/eip-3541#test-cases
        decode_hex("0x60ef60005360016000f3"),
        decode_hex("0x60ef60005360026000f3"),
        decode_hex("0x60ef60005360036000f3"),
        decode_hex("0x60ef60005360206000f3"),
    ),
)
def test_state_revert_on_reserved_0xEF_byte_for_create_transaction_post_london(
    london_plus_miner, funded_address, funded_address_private_key, data
):
    chain = london_plus_miner
    vm = chain.get_vm()
    initial_block_header = chain.get_block().header
    initial_balance = vm.state.get_balance(funded_address)

    assert (
        initial_balance > 1000000
    )  # arbitrary number, enough for all our transactions

    # positive test case from https://eips.ethereum.org/EIPS/eip-3541#test-cases
    create_successful_contract_transaction = new_dynamic_fee_transaction(
        vm=vm,
        from_=funded_address,
        to=Address(b""),
        amount=0,
        private_key=funded_address_private_key,
        gas=53354,
        max_priority_fee_per_gas=100,
        max_fee_per_gas=100000000000,
        nonce=0,
        data=decode_hex("0x60fe60005360016000f3"),
    )

    block_import, _, computations = chain.mine_all(
        [create_successful_contract_transaction],
        gas_limit=84081,
    )
    successful_create_computation = computations[0]
    successful_create_computation_state = successful_create_computation.state

    mined_header = block_import.imported_block.header
    gas_used = mined_header.gas_used
    mined_txn = block_import.imported_block.transactions[0]
    new_balance = successful_create_computation_state.get_balance(funded_address)

    assert successful_create_computation.is_success
    assert successful_create_computation_state.get_nonce(funded_address) == 1
    assert gas_used == 53354
    fees_consumed = (mined_txn.max_priority_fee_per_gas * gas_used) + (
        initial_block_header.base_fee_per_gas * gas_used
    )
    # successful txn consumes gas and fees:
    assert new_balance == initial_balance - fees_consumed

    # test the parametrized negative cases
    create_contract_txn_reserved_byte = new_dynamic_fee_transaction(
        vm=vm,
        from_=funded_address,
        to=Address(b""),
        amount=0,
        private_key=funded_address_private_key,
        gas=60000,
        max_priority_fee_per_gas=100,
        max_fee_per_gas=100000000000,
        nonce=1,
        data=data,
    )

    block_import, _, computations = chain.mine_all(
        [create_contract_txn_reserved_byte], gas_limit=84082
    )

    reverted_computation = computations[0]
    mined_header = block_import.imported_block.header

    assert reverted_computation.is_error
    assert "0xef" in repr(reverted_computation.error).lower()

    # reverted txn consumes the gas:
    assert mined_header.gas_used == 60000


@pytest.mark.parametrize("code, data", EIP_3541_CREATE_AND_CREATE2_REVERT_TEST_CASES)
def test_state_does_not_revert_on_reserved_0xEF_byte_for_CREATE_and_CREATE2_pre_london(
    pre_london_miner,
    funded_address,
    code,
    data,
):
    chain = pre_london_miner
    vm = chain.get_vm()

    computation = vm.execute_bytecode(
        origin=funded_address,
        to=funded_address,
        sender=funded_address,
        value=0,
        code=code,
        data=data,
        gas=40000,
        gas_price=1,
    )

    if computation.is_error:
        assert isinstance(computation.error, InvalidInstruction)
        # pre-CREATE2 vms will not recognize the CREATE2 opcode:
        assert "0xf5" in repr(computation.error).lower()
        assert vm.fork in (_.fork for _ in MINING_MAINNET_VMS[:5])

    else:
        assert computation.is_success
        # assert only the appropriate gas is consumed, not all the gas.
        # This falls within a range
        assert 32261 <= computation.get_gas_used() <= 38470
        assert computation.get_gas_refund() == 0


@pytest.mark.parametrize(
    "data",
    (
        # negative test cases from https://eips.ethereum.org/EIPS/eip-3541#test-cases
        decode_hex("0x60ef60005360016000f3"),
        decode_hex("0x60ef60005360026000f3"),
        decode_hex("0x60ef60005360036000f3"),
        decode_hex("0x60ef60005360206000f3"),
    ),
)
def test_state_does_not_revert_on_reserved_0xEF_byte_for_create_transaction_pre_london(
    pre_london_miner, funded_address, funded_address_private_key, data
):
    chain = pre_london_miner
    vm = chain.get_vm()
    initial_balance = vm.state.get_balance(funded_address)

    # test the parametrized negative cases
    create_contract_txn_0xef_byte = new_transaction(
        vm=vm,
        from_=funded_address,
        to=Address(b""),
        amount=0,
        private_key=funded_address_private_key,
        gas=60000,
        nonce=0,
        data=data,
    )

    block_import, _, computations = chain.mine_all(
        [create_contract_txn_0xef_byte], gas_limit=99904
    )

    computation = computations[0]
    mined_header = block_import.imported_block.header
    txn = block_import.imported_block.transactions[0]
    end_balance = computation.state.get_balance(funded_address)

    assert computation.is_success
    assert computation.state.get_nonce(funded_address) == 1
    # txn consumes gas and fees
    assert end_balance == initial_balance - (txn.gas_price * mined_header.gas_used)
