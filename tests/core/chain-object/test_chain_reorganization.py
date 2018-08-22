import pytest

from cytoolz import pipe

from eth.chains.base import MiningChain

from eth.tools.builder.chain import api


@pytest.fixture(params=api.mainnet_fork_at_fns)
def base_chain(request):
    chain = pipe(
        MiningChain,
        request.param(0),
        api.disable_pow_check(),
        api.genesis(),
    )

    return chain


@pytest.fixture
def chain(base_chain):
    chain = pipe(
        base_chain,
        api.mine_blocks(3),
    )
    assert chain.get_canonical_head().block_number == 3
    return chain


def test_import_block_with_reorg(chain, funded_address_private_key):
    # mine ahead 3 blocks on the fork chain
    fork_chain = pipe(
        chain,
        api.copy(),
        api.mine_block(extra_data=b'fork-it'),
        api.mine_blocks(2),
    )
    # mine ahead 2 blocks on the main chain
    pipe(
        chain,
        api.mine_blocks(2)
    )

    block_4 = chain.get_canonical_block_by_number(4)
    f_block_4 = fork_chain.get_canonical_block_by_number(4)

    assert f_block_4.number == block_4.number == 4
    assert f_block_4 != block_4
    assert f_block_4.header.difficulty <= block_4.header.difficulty

    block_5 = chain.get_canonical_block_by_number(5)
    f_block_5 = fork_chain.get_canonical_block_by_number(5)

    assert f_block_5.number == block_5.number == 5
    assert f_block_5 != block_5
    assert f_block_5.header.difficulty <= block_5.header.difficulty

    f_block_6 = fork_chain.get_canonical_block_by_number(6)
    pre_reorg_chain_head = chain.header

    # now we proceed to import the blocks from the fork chain into the main
    # chain.  Blocks 4 and 5 should import resulting in no re-organization.
    for block in (f_block_4, f_block_5):
        _, new_canonical_blocks, old_canonical_blocks = chain.import_block(block)
        assert not new_canonical_blocks
        assert not old_canonical_blocks
        # ensure that the main chain head has not changed.
        assert chain.header == pre_reorg_chain_head

    # now we import block 6 from the fork chain.  This should cause a re-org.
    _, new_canonical_blocks, old_canonical_blocks = chain.import_block(f_block_6)
    assert new_canonical_blocks == (f_block_4, f_block_5, f_block_6)
    assert old_canonical_blocks == (block_4, block_5)

    assert chain.get_canonical_head() == f_block_6.header


def test_import_block_with_reorg_with_current_head_as_uncle(
        chain,
        funded_address_private_key):
    """
    https://github.com/ethereum/py-evm/issues/1185
    """
    def converge_split_fn(results):
        chain_a = results[0][-1]
        chain_b = results[1][-1]

        # the chain head from the main chain will become an uncle once we
        # import the fork chain blocks.
        uncle = chain_a.get_canonical_head()

        pipe(
            chain_b,
            api.mine_block(uncles=(uncle,)),
        )
        head = chain_b.get_canonical_head()
        block_a = chain_b.get_canonical_block_by_number(head.block_number - 1)
        block_b = chain_b.get_canonical_block_by_number(head.block_number)

        return pipe(
            chain_a,
            api.import_block(block_a),
            api.import_block(block_b),  # the block with the uncle.
        )

    chain = pipe(
        chain,
        api.chain_split(
            (api.mine_block(),),  # this will be the 'uncle'
            (api.mine_block(extra_data=b'fork-it'),),
            exit_fn=converge_split_fn,
        ),
    )

    header = chain.get_canonical_head()
    block = chain.get_canonical_block_by_number(header.block_number)

    assert len(block.uncles) == 1
