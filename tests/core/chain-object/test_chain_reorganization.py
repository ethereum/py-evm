import pytest

from eth.chains.base import (
    MiningChain,
)
from eth.tools.builder.chain import (
    api,
)


@pytest.fixture(params=api.mining_mainnet_fork_at_fns)
def mining_base_chain(request):
    if request.param is api.homestead_at:
        fork_fns = (request.param(0), api.dao_fork_at(0))
    else:
        fork_fns = (request.param(0),)

    chain = api.build(
        MiningChain,
        *fork_fns,
        api.disable_pow_check(),
        api.genesis(),
    )

    return chain


@pytest.fixture
def mining_chain(mining_base_chain):
    chain = api.build(
        mining_base_chain,
        api.mine_blocks(3),
    )
    assert chain.get_canonical_head().block_number == 3
    return chain


def test_import_block_with_reorg(mining_chain, funded_address_private_key):
    # mine ahead 3 blocks on the fork chain
    fork_chain = api.build(
        mining_chain,
        api.copy(),
        api.mine_block(extra_data=b"fork-it"),
        api.mine_blocks(2),
    )
    # mine ahead 2 blocks on the main chain
    main_chain = api.build(mining_chain, api.mine_blocks(2))

    block_4 = main_chain.get_canonical_block_by_number(4)
    f_block_4 = fork_chain.get_canonical_block_by_number(4)

    assert f_block_4.number == block_4.number == 4
    assert f_block_4 != block_4
    assert f_block_4.header.difficulty <= block_4.header.difficulty

    block_5 = main_chain.get_canonical_block_by_number(5)
    f_block_5 = fork_chain.get_canonical_block_by_number(5)

    assert f_block_5.number == block_5.number == 5
    assert f_block_5 != block_5
    assert f_block_5.header.difficulty <= block_5.header.difficulty

    f_block_6 = fork_chain.get_canonical_block_by_number(6)
    pre_reorg_chain_head = main_chain.header

    # now we proceed to import the blocks from the fork chain into the main
    # chain.  Blocks 4 and 5 should import resulting in no re-organization.
    for block in (f_block_4, f_block_5):
        block_import_result = main_chain.import_block(block)
        assert not block_import_result.new_canonical_blocks
        assert not block_import_result.old_canonical_blocks
        # ensure that the main chain head has not changed.
        assert main_chain.header == pre_reorg_chain_head

    # now we import block 6 from the fork chain.  This should cause a re-org.
    block_import_result = main_chain.import_block(f_block_6)
    assert block_import_result.new_canonical_blocks == (f_block_4, f_block_5, f_block_6)
    assert block_import_result.old_canonical_blocks == (block_4, block_5)

    assert main_chain.get_canonical_head() == f_block_6.header


def test_import_block_with_reorg_with_current_head_as_uncle(
    mining_chain, funded_address_private_key
):
    """
    https://github.com/ethereum/py-evm/issues/1185
    """

    main_chain, fork_chain = api.build(
        mining_chain,
        api.chain_split(
            (api.mine_block(),),  # this will be the 'uncle'
            (api.mine_block(extra_data=b"fork-it"),),
        ),
    )

    # the chain head from the main chain will become an uncle once we
    # import the fork chain blocks.
    uncle = main_chain.get_canonical_head()

    fork_chain = api.build(
        fork_chain,
        api.mine_block(uncles=(uncle,)),
    )
    head = fork_chain.get_canonical_head()
    block_a = fork_chain.get_canonical_block_by_number(head.block_number - 1)
    block_b = fork_chain.get_canonical_block_by_number(head.block_number)

    final_chain = api.build(
        main_chain,
        api.import_block(block_a),
        api.import_block(block_b),  # the block with the uncle.
    )

    header = final_chain.get_canonical_head()
    block = final_chain.get_canonical_block_by_number(header.block_number)

    assert len(block.uncles) == 1
