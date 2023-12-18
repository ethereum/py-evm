import pytest

from eth.chains.base import (
    MiningChain,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.db.backends.memory import (
    MemoryDB,
)


@pytest.fixture
def chain(chain_without_block_validation):
    if not isinstance(chain_without_block_validation, MiningChain):
        pytest.skip("only valid on mining chains")
    return chain_without_block_validation


@pytest.fixture
def fork_chain(chain):
    # make a duplicate chain with no shared state
    fork_db = AtomicDB(MemoryDB(chain.chaindb.db.wrapped_db.kv_store.copy()))
    fork_chain = type(chain)(fork_db, chain.header)

    return fork_chain


@pytest.mark.parametrize(
    "limit",
    (0, 1, 2, 5),
)
def test_chain_get_ancestors_from_genesis_block(chain, limit):
    header = chain.get_canonical_head()
    assert header.block_number == 0

    ancestors = chain.get_ancestors(limit, header)
    assert ancestors == ()


def test_chain_get_ancestors_from_block_1(chain):
    genesis = chain.get_canonical_block_by_number(0)
    block_1 = chain.mine_block()
    header = block_1.header
    assert header.block_number == 1

    assert chain.get_ancestors(0, header) == ()
    assert chain.get_ancestors(1, header) == (genesis,)
    assert chain.get_ancestors(2, header) == (genesis,)
    assert chain.get_ancestors(5, header) == (genesis,)


def test_chain_get_ancestors_from_block_5(chain):
    genesis = chain.get_canonical_block_by_number(0)
    (
        block_1,
        block_2,
        block_3,
        block_4,
        block_5,
    ) = (chain.mine_block() for _ in range(5))

    header = block_5.header
    assert header.block_number == 5

    assert chain.get_ancestors(0, header) == ()
    assert chain.get_ancestors(1, header) == (block_4,)
    assert chain.get_ancestors(2, header) == (block_4, block_3)
    assert chain.get_ancestors(3, header) == (block_4, block_3, block_2)
    assert chain.get_ancestors(4, header) == (block_4, block_3, block_2, block_1)
    assert chain.get_ancestors(5, header) == (
        block_4,
        block_3,
        block_2,
        block_1,
        genesis,
    )
    assert chain.get_ancestors(6, header) == (
        block_4,
        block_3,
        block_2,
        block_1,
        genesis,
    )
    assert chain.get_ancestors(10, header) == (
        block_4,
        block_3,
        block_2,
        block_1,
        genesis,
    )


def test_chain_get_ancestors_for_fork_chains(chain, fork_chain):
    genesis = chain.get_canonical_block_by_number(0)
    (
        block_1,
        block_2,
        block_3,
    ) = (chain.mine_block() for _ in range(3))
    (
        f_block_1,
        f_block_2,
        f_block_3,
    ) = (fork_chain.mine_block() for _ in range(3))

    assert block_1 == f_block_1
    assert block_2 == f_block_2
    assert block_3 == f_block_3

    # force the fork chain to diverge
    fork_chain.header = fork_chain.header.copy(extra_data=b"fork-it!")

    # mine ahead a bit further on both chains.
    (
        block_4,
        block_5,
        block_6,
    ) = (chain.mine_block() for _ in range(3))
    (
        f_block_4,
        f_block_5,
        f_block_6,
    ) = (fork_chain.mine_block() for _ in range(3))

    # import the fork blocks into the main chain (ensuring they don't cause a reorg)
    block_import_result = chain.import_block(f_block_4)
    new_chain = block_import_result.new_canonical_blocks
    assert new_chain == ()

    block_import_result = chain.import_block(f_block_5)
    new_chain = block_import_result.new_canonical_blocks
    assert new_chain == ()

    # check with a block that has been imported
    assert chain.get_ancestors(0, f_block_5.header) == ()
    assert chain.get_ancestors(1, f_block_5.header) == (f_block_4,)
    assert chain.get_ancestors(2, f_block_5.header) == (f_block_4, block_3)
    assert chain.get_ancestors(3, f_block_5.header) == (f_block_4, block_3, block_2)
    assert chain.get_ancestors(4, f_block_5.header) == (
        f_block_4,
        block_3,
        block_2,
        block_1,
    )
    assert chain.get_ancestors(5, f_block_5.header) == (
        f_block_4,
        block_3,
        block_2,
        block_1,
        genesis,
    )
    # check that when we hit genesis it self limits
    assert chain.get_ancestors(6, f_block_5.header) == (
        f_block_4,
        block_3,
        block_2,
        block_1,
        genesis,
    )
    assert chain.get_ancestors(20, f_block_5.header) == (
        f_block_4,
        block_3,
        block_2,
        block_1,
        genesis,
    )

    # check with a block that has NOT been imported
    assert chain.get_ancestors(0, f_block_6.header) == ()
    assert chain.get_ancestors(1, f_block_6.header) == (f_block_5,)
    assert chain.get_ancestors(2, f_block_6.header) == (f_block_5, f_block_4)
    assert chain.get_ancestors(3, f_block_6.header) == (f_block_5, f_block_4, block_3)
    assert chain.get_ancestors(4, f_block_6.header) == (
        f_block_5,
        f_block_4,
        block_3,
        block_2,
    )
    assert chain.get_ancestors(5, f_block_6.header) == (
        f_block_5,
        f_block_4,
        block_3,
        block_2,
        block_1,
    )
    assert chain.get_ancestors(6, f_block_6.header) == (
        f_block_5,
        f_block_4,
        block_3,
        block_2,
        block_1,
        genesis,
    )
    # check that when we hit genesis it self limits
    assert chain.get_ancestors(7, f_block_6.header) == (
        f_block_5,
        f_block_4,
        block_3,
        block_2,
        block_1,
        genesis,
    )
    assert chain.get_ancestors(20, f_block_6.header) == (
        f_block_5,
        f_block_4,
        block_3,
        block_2,
        block_1,
        genesis,
    )
