import pytest

from cytoolz import pipe

from eth_utils import ValidationError

from eth.chains.base import (
    Chain,
    MiningChain,
)
from eth.tools.builder.chain import (
    frontier_at,
    genesis,
    mine_block,
    mine_blocks,
    disable_pow_check,
    at_block_number,
    copy,
    import_block,
    import_blocks,
)


MINING_CHAIN_PARAMS = (
    MiningChain,
    frontier_at(0),
    disable_pow_check,
    genesis(),
)


@pytest.fixture
def mining_chain():
    return pipe(*MINING_CHAIN_PARAMS)


REGULAR_CHAIN_PARAMS = (
    Chain,
    frontier_at(0),
    genesis(),
)


@pytest.fixture
def regular_chain():
    return pipe(*REGULAR_CHAIN_PARAMS)


@pytest.fixture(params=(MINING_CHAIN_PARAMS, REGULAR_CHAIN_PARAMS))
def any_chain(request):
    return pipe(*request.param)


def test_chain_builder_build_single_default_block(mining_chain):
    chain = pipe(
        mining_chain,
        mine_block(),
    )

    header = chain.get_canonical_head()
    assert header.block_number == 1


def test_chain_builder_build_two_default_blocks(mining_chain):
    chain = pipe(
        mining_chain,
        mine_block(),
        mine_block(),
    )

    header = chain.get_canonical_head()
    assert header.block_number == 2


def test_chain_builder_build_mine_multiple_blocks(mining_chain):
    chain = pipe(
        mining_chain,
        mine_blocks(5),
    )

    header = chain.get_canonical_head()
    assert header.block_number == 5


def test_chain_builder_mine_block_with_parameters(mining_chain):
    chain = pipe(
        mining_chain,
        mine_block(extra_data=b'test-setting-extra-data'),
    )

    header = chain.get_canonical_head()
    assert header.extra_data == b'test-setting-extra-data'


def test_chain_builder_mine_block_only_on_mining_chain(regular_chain):
    with pytest.raises(ValidationError, match="MiningChain"):
        mine_block()(regular_chain)


def test_chain_builder_mine_multiple_blocks_only_on_mining_chain(regular_chain):
    with pytest.raises(ValidationError, match="MiningChain"):
        mine_blocks(5)(regular_chain)


def test_chain_builder_fork_chain(mining_chain):
    pre_fork_chain = pipe(
        mining_chain,
        mine_block(),  # 1
        mine_block(),  # 2
        mine_block(),  # 3
    )
    block_1 = pre_fork_chain.get_canonical_block_by_number(1)
    block_2 = pre_fork_chain.get_canonical_block_by_number(2)
    block_3 = pre_fork_chain.get_canonical_block_by_number(3)

    chain = pipe(
        pre_fork_chain,
        copy(),
        at_block_number(2),
        mine_block(extra_data=b'fork-it!'),  # fork 3
        mine_block(),  # fork 4
        mine_block(),  # fork 5
    )

    # ensure that our chain is ahead of the pre_fork_chain
    head = chain.get_canonical_head()
    assert head.block_number == 5

    pre_fork_head = pre_fork_chain.get_canonical_head()
    assert pre_fork_head.block_number == 3

    f_block_1 = chain.get_canonical_block_by_number(1)
    f_block_2 = chain.get_canonical_block_by_number(2)
    f_block_3 = chain.get_canonical_block_by_number(3)

    # verify that the fork diverges from the pre_fork_chain
    assert f_block_1 == block_1
    assert f_block_2 == block_2
    assert f_block_3 != block_3


def test_chain_builder_build_uncle_fork(mining_chain):
    chain = pipe(
        mining_chain,
        mine_block(),  # 1
        mine_block(),  # 2
    )

    fork_chain = pipe(
        chain,
        at_block_number(1),
        mine_block(extra_data=b'fork-it!'),  # fork 2
    )

    # we don't use canonical head here because the fork chain is non-canonical.
    uncle = fork_chain.get_block_header_by_hash(fork_chain.header.parent_hash)
    assert uncle.block_number == 2
    assert uncle != chain.get_canonical_head()

    pipe(
        chain,
        mine_block(uncles=[uncle]),  # 3
    )

    header = chain.get_canonical_head()
    block = chain.get_block_by_hash(header.hash)
    assert len(block.uncles) == 1
    assert block.uncles[0] == uncle


def test_chain_import_block_single(mining_chain):
    temp_chain = pipe(
        mining_chain,
        copy(),
        mine_blocks(3),
    )
    block_1, block_2, block_3 = (
        temp_chain.get_canonical_block_by_number(1),
        temp_chain.get_canonical_block_by_number(2),
        temp_chain.get_canonical_block_by_number(3),
    )

    chain = pipe(
        mining_chain,
        import_block(block_1),
        import_block(block_2),
        import_block(block_3),
    )
    head = chain.get_canonical_head()
    assert head == block_3.header


def test_chain_import_blocks_many(mining_chain):
    temp_chain = pipe(
        mining_chain,
        copy(),
        mine_blocks(3),
    )
    block_1, block_2, block_3 = (
        temp_chain.get_canonical_block_by_number(1),
        temp_chain.get_canonical_block_by_number(2),
        temp_chain.get_canonical_block_by_number(3),
    )

    chain = pipe(
        mining_chain,
        import_blocks(block_1, block_2, block_3),
    )
    head = chain.get_canonical_head()
    assert head == block_3.header
