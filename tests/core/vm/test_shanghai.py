import pytest

from eth.chains.base import (
    MiningChain,
)
from eth.consensus import (
    NoProofConsensus,
)
from eth.vm.forks import (
    ShanghaiVM,
)
from eth.vm.forks.shanghai.withdrawals import (
    Withdrawal,
)


@pytest.fixture
def shanghai_at_genesis(base_db, genesis_state):
    return MiningChain.configure(
        __name__="ShanghaiAt1",
        vm_configuration=((0, ShanghaiVM.configure(consensus_class=NoProofConsensus)),),
        chain_id=1337,
    ).from_genesis(
        base_db,
        {},
        genesis_state,
    )


def test_withdrawals_are_stored_in_chain_db(shanghai_at_genesis):
    chain = shanghai_at_genesis
    vm = chain.get_vm()

    chain.mine_block()  # block 1

    withdrawals = [
        Withdrawal(
            index=i, validator_index=i + 1, address=vm.state.coinbase, amount=i * 10
        )
        for i in range(5)
    ]
    assert len(withdrawals) == 5
    block_import, _, _ = chain.mine_all([], withdrawals=withdrawals)
    block2 = block_import.imported_block

    # assert coinbase balance is equal to sum of withdrawals in wei (gwei == 10**9 wei)
    assert chain.get_vm().state.get_balance(vm.state.coinbase) == sum(
        [w.amount * 10**9 for w in withdrawals]
    )

    chain.mine_block()  # block 3
    chain.mine_block()  # block 4

    retrieved_block2 = chain.get_block_by_hash(block2.hash)

    # check we've stored withdrawals appropriately and are able to retrieve them

    # retrieve block and retrieve withdrawals from block
    retrieved_withdrawals_from_retrieved_block = retrieved_block2.withdrawals

    # retrieve withdrawals from chain db
    retrieved_withdrawals_from_chain_db = chain.chaindb.get_block_withdrawals(
        block2.header
    )

    assert len(retrieved_withdrawals_from_retrieved_block) == len(withdrawals)
    assert len(retrieved_withdrawals_from_chain_db) == len(withdrawals)

    for withdrawal in retrieved_withdrawals_from_retrieved_block:
        assert withdrawal in withdrawals

    for db_withdrawal in retrieved_withdrawals_from_chain_db:
        assert db_withdrawal in withdrawals
