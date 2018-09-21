import pytest

from eth_utils import (
    to_wei
)

from eth.chains.base import (
    MiningChain
)
from eth.tools.builder.chain import (
    at_block_number,
    build,
    disable_pow_check,
    mine_block,
    byzantium_at,
    frontier_at,
    homestead_at,
    spurious_dragon_at,
    tangerine_whistle_at,
    constantinople_at,
    genesis,
)


@pytest.mark.parametrize(
    'vm_fn, miner_1_balance, miner_2_balance',
    (
        (frontier_at, 15.15625, 4.375),
        (homestead_at, 15.15625, 4.375),
        (tangerine_whistle_at, 15.15625, 4.375),
        (spurious_dragon_at, 15.15625, 4.375),
        (byzantium_at, 9.09375, 2.625),
        (constantinople_at, 6.0625, 1.75),
    )
)
def test_rewards(vm_fn, miner_1_balance, miner_2_balance):

    OTHER_MINER_ADDRESS = 20 * b'\x01'
    TOTAL_BLOCKS_CANONICAL_CHAIN = 3

    chain = build(
        MiningChain,
        vm_fn(0),
        disable_pow_check(),
        genesis(),
        mine_block(),  # 1
        mine_block(),  # 2
    )

    fork_chain = build(
        chain,
        at_block_number(1),
        mine_block(extra_data=b'fork-it!', coinbase=OTHER_MINER_ADDRESS),  # fork 2
    )

    # we don't use canonical head here because the fork chain is non-canonical.
    uncle = fork_chain.get_block_header_by_hash(fork_chain.header.parent_hash)
    assert uncle.block_number == 2
    assert uncle != chain.get_canonical_head()

    chain = build(
        chain,
        mine_block(uncles=[uncle]),  # 3
    )

    header = chain.get_canonical_head()
    block = chain.get_block_by_hash(header.hash)
    assert len(block.uncles) == 1
    assert block.uncles[0] == uncle

    vm = chain.get_vm()
    coinbase_balance = vm.state.account_db.get_balance(block.header.coinbase)
    other_miner_balance = vm.state.account_db.get_balance(uncle.coinbase)

    # We first test if the balance matches what we would determine
    # if we made all the API calls involved ourselves.
    assert coinbase_balance == (vm.get_block_reward() *
                                TOTAL_BLOCKS_CANONICAL_CHAIN +
                                vm.get_nephew_reward())
    assert other_miner_balance == vm.get_uncle_reward(block.number, uncle)

    # But we also ensure the balance matches the numbers that we calculated on paper
    assert coinbase_balance == to_wei(miner_1_balance, 'ether')
    assert other_miner_balance == to_wei(miner_2_balance, 'ether')
