import pytest

from eth import constants
from eth.consensus.noproof import NoProofConsensus
from eth.chains.base import MiningChain
from eth.chains.mainnet import (
    MAINNET_VMS,
)
from eth.vm.forks import BerlinVM
from eth.tools.factories.transaction import (
    new_transaction
)


# VMs starting at London
@pytest.fixture(params=MAINNET_VMS[9:])
def london_plus_miner(request, base_db, genesis_state):
    klass = MiningChain.configure(
        __name__='LondonAt1',
        vm_configuration=(
            (
                constants.GENESIS_BLOCK_NUMBER,
                BerlinVM.configure(consensus_class=NoProofConsensus),
            ),
            (
                constants.GENESIS_BLOCK_NUMBER + 1,
                request.param.configure(consensus_class=NoProofConsensus),
            ),
        ),
        chain_id=1337,
    )
    header_fields = dict(
        difficulty=1,
        gas_limit=21000 * 2,  # block limit is hit with two transactions
    )
    # On the first London+ block, it will double the block limit so that it
    #   can precisely hold 4 transactions.
    return klass.from_genesis(base_db, header_fields, genesis_state)


@pytest.mark.parametrize(
    'num_txns, expected_base_fee',
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
        london_plus_miner, funded_address, funded_address_private_key, num_txns, expected_base_fee):
    chain = london_plus_miner
    FOUR_TXN_GAS_LIMIT = 21000 * 4
    assert chain.header.gas_limit == FOUR_TXN_GAS_LIMIT

    vm = chain.get_vm()
    txns = [
        new_transaction(
            vm,
            funded_address,
            b'\x00' * 20,
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
    assert mined_header.base_fee_per_gas == 10 ** 9  # Initialize at 1 gwei

    block_import, _, _ = chain.mine_all([], gas_limit=FOUR_TXN_GAS_LIMIT)
    mined_header = block_import.imported_block.header
    assert mined_header.gas_limit == FOUR_TXN_GAS_LIMIT
    assert mined_header.gas_used == 0
    # Check that the base fee evolved correctly, depending on how much gas was used in the parent
    assert mined_header.base_fee_per_gas == expected_base_fee
