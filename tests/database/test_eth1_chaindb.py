from eth_hash.auto import (
    keccak,
)
from hypothesis import (
    given,
    strategies as st,
)
import pytest
import rlp

from eth._utils.address import (
    force_bytes_to_address,
)
from eth.chains.base import (
    MiningChain,
)
from eth.constants import (
    BLANK_ROOT_HASH,
    ZERO_ADDRESS,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.db.chain import (
    ChainDB,
)
from eth.db.chain_gaps import (
    GENESIS_CHAIN_GAPS,
)
from eth.db.schema import (
    SchemaV1,
)
from eth.exceptions import (
    BlockNotFound,
    CheckpointsMustBeCanonical,
    HeaderNotFound,
    ParentNotFound,
    ReceiptNotFound,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.tools.builder.chain import (
    api,
)
from eth.tools.factories.transaction import (
    new_access_list_transaction,
    new_transaction,
)
from eth.tools.rlp import (
    assert_headers_eq,
)
from eth.vm.forks import (
    BerlinVM,
    LondonVM,
)
from eth.vm.forks.frontier.blocks import (
    FrontierBlock,
)
from eth.vm.forks.homestead.blocks import (
    HomesteadBlock,
)

A_ADDRESS = b"\xaa" * 20
B_ADDRESS = b"\xbb" * 20


def set_empty_root(chaindb, header):
    return header.copy(
        transaction_root=BLANK_ROOT_HASH,
        receipt_root=BLANK_ROOT_HASH,
        state_root=BLANK_ROOT_HASH,
    )


@pytest.fixture
def chaindb(base_db):
    return ChainDB(base_db)


@pytest.fixture(params=[0, 10, 999])
def header(request):
    block_number = request.param
    difficulty = 1
    gas_limit = 1
    return BlockHeader(difficulty, block_number, gas_limit)


@pytest.fixture(params=[FrontierBlock, HomesteadBlock])
def block(request, header):
    return request.param(header)


@pytest.fixture
def chain(chain_without_block_validation):
    if not isinstance(chain_without_block_validation, MiningChain):
        pytest.skip("these tests require a mining chain implementation")
    else:
        return chain_without_block_validation


def test_chaindb_add_block_number_to_hash_lookup(chaindb, block):
    block_number_to_hash_key = SchemaV1.make_block_number_to_hash_lookup_key(
        block.number
    )
    assert not chaindb.exists(block_number_to_hash_key)
    assert chaindb.get_chain_gaps() == GENESIS_CHAIN_GAPS
    chaindb.persist_block(block)
    assert chaindb.exists(block_number_to_hash_key)


@pytest.mark.parametrize(
    "has_uncle, has_transaction, can_fetch_block",
    (
        # Uncle block gets de-canonicalized by a header that has another uncle
        (
            True,
            False,
            False,
        ),
        # Uncle block gets de-canonicalized by a header that has transactions
        (
            False,
            True,
            False,
        ),
        # Has uncle and transactions
        (
            True,
            True,
            False,
        ),
        # Uncle block gets de-canonicalized by a header that has no uncles nor
        # transactions which means this is a "Header-only" block. Even though we
        # technically do not need to re-open a gap here, we don't have a good way
        # of detecting that special case and hence open a gap.
        (
            False,
            False,
            True,
        ),
    ),
)
def test_block_gap_tracking(
    chain,
    funded_address,
    funded_address_private_key,
    has_uncle,
    has_transaction,
    can_fetch_block,
):
    # Mine three common blocks
    common_chain = api.build(
        chain,
        api.mine_blocks(3),
    )

    assert common_chain.get_canonical_head().block_number == 3
    assert common_chain.chaindb.get_chain_gaps() == ((), 4)

    tx = new_transaction(
        common_chain.get_vm(),
        from_=funded_address,
        to=ZERO_ADDRESS,
        private_key=funded_address_private_key,
    )
    uncle = api.build(
        common_chain, api.mine_block()
    ).get_canonical_block_header_by_number(4)
    uncles = [uncle] if has_uncle else []
    transactions = [tx] if has_transaction else []

    # Split and have the main chain mine four blocks, the uncle chain two blocks
    main_chain, uncle_chain = api.build(
        common_chain,
        api.chain_split(
            (
                # We have four different scenarios for our replaced blocks:
                #   1. Replaced by a trivial block without uncles or transactions
                #   2. Replaced by a block with transactions
                #   3. Replaced by a block with uncles
                #   4. 2 and 3 combined
                api.mine_block(uncles=uncles, transactions=transactions),
                api.mine_block(),
                api.mine_block(),
                api.mine_block(),
            ),
            # This will be the uncle chain
            (
                api.mine_block(extra_data=b"fork-it"),
                api.mine_block(),
            ),
        ),
    )

    main_head = main_chain.get_canonical_head()
    assert main_head.block_number == 7
    assert uncle_chain.get_canonical_head().block_number == 5

    assert main_chain.chaindb.get_chain_gaps() == ((), 8)
    assert uncle_chain.chaindb.get_chain_gaps() == ((), 6)

    main_header_6 = main_chain.chaindb.get_canonical_block_header_by_number(6)
    main_header_6_score = main_chain.chaindb.get_score(main_header_6.hash)

    gap_chain = api.copy(common_chain)
    assert gap_chain.get_canonical_head() == common_chain.get_canonical_head()

    gap_chain.chaindb.persist_checkpoint_header(main_header_6, main_header_6_score)
    # We created a gap in the chain of headers
    assert gap_chain.chaindb.get_header_chain_gaps() == (((4, 5),), 7)
    # ...but not in the chain of blocks (yet!)
    assert gap_chain.chaindb.get_chain_gaps() == ((), 4)
    block_7 = main_chain.get_canonical_block_by_number(7)
    block_7_receipts = block_7.get_receipts(main_chain.chaindb)
    # Persist block 7 on top of the checkpoint
    gap_chain.chaindb.persist_unexecuted_block(block_7, block_7_receipts)
    assert gap_chain.chaindb.get_header_chain_gaps() == (((4, 5),), 8)
    # Now we have a gap in the chain of blocks, too
    assert gap_chain.chaindb.get_chain_gaps() == (((4, 6),), 8)

    # Overwriting header 3 doesn't cause us to re-open a block gap
    gap_chain.chaindb.persist_header_chain(
        [main_chain.chaindb.get_canonical_block_header_by_number(3)]
    )
    assert gap_chain.chaindb.get_chain_gaps() == (((4, 6),), 8)

    # Now get the uncle block
    uncle_block = uncle_chain.get_canonical_block_by_number(4)
    uncle_block_receipts = uncle_block.get_receipts(uncle_chain.chaindb)

    # Put the uncle block in the gap
    gap_chain.chaindb.persist_unexecuted_block(uncle_block, uncle_block_receipts)
    assert gap_chain.chaindb.get_header_chain_gaps() == (((5, 5),), 8)
    assert gap_chain.chaindb.get_chain_gaps() == (((5, 6),), 8)

    # Trying to save another uncle errors as its header
    # isn't the parent of the checkpoint
    second_uncle = uncle_chain.get_canonical_block_by_number(5)
    second_uncle_receipts = second_uncle.get_receipts(uncle_chain.chaindb)
    with pytest.raises(CheckpointsMustBeCanonical):
        gap_chain.chaindb.persist_unexecuted_block(second_uncle, second_uncle_receipts)

    # Now close the gap in the header chain with the actual correct headers
    actual_headers = [
        main_chain.chaindb.get_canonical_block_header_by_number(block_number)
        for block_number in range(4, 7)
    ]
    gap_chain.chaindb.persist_header_chain(actual_headers)
    # No more gaps in the header chain
    assert gap_chain.chaindb.get_header_chain_gaps() == ((), 8)
    # We detected the de-canonicalized uncle and re-opened the block gap
    assert gap_chain.chaindb.get_chain_gaps() == (((4, 6),), 8)

    if can_fetch_block:
        # We can fetch the block even if the gap tracking reports it as missing if the
        # block is a "trivial" block, meaning one that doesn't have transactions nor
        # uncles and hence can be loaded by just the header alone.
        block_4 = gap_chain.get_canonical_block_by_number(4)
        assert block_4 == main_chain.get_canonical_block_by_number(4)
    else:
        # The uncle block was implicitly de-canonicalized with its header,
        # hence we can not fetch it any longer.
        with pytest.raises(BlockNotFound):
            gap_chain.get_canonical_block_by_number(4)
        # Add the missing block and assert the gap shrinks
        assert gap_chain.chaindb.get_chain_gaps() == (((4, 6),), 8)
        block_4 = main_chain.get_canonical_block_by_number(4)
        block_4_receipts = block_4.get_receipts(main_chain.chaindb)
        gap_chain.chaindb.persist_unexecuted_block(block_4, block_4_receipts)
        assert gap_chain.chaindb.get_chain_gaps() == (((5, 6),), 8)


def test_chaindb_persist_header(chaindb, header):
    with pytest.raises(HeaderNotFound):
        chaindb.get_block_header_by_hash(header.hash)
    number_to_hash_key = SchemaV1.make_block_hash_to_score_lookup_key(header.hash)
    assert not chaindb.exists(number_to_hash_key)

    chaindb.persist_header(header)

    assert chaindb.get_block_header_by_hash(header.hash) == header
    assert chaindb.exists(number_to_hash_key)


@given(seed=st.binary(min_size=32, max_size=32))
def test_chaindb_persist_header_unknown_parent(chaindb, header, seed):
    n_header = header.copy(parent_hash=keccak(seed))
    with pytest.raises(ParentNotFound):
        chaindb.persist_header(n_header)


def test_chaindb_persist_block(chaindb, block):
    block = block.copy(header=set_empty_root(chaindb, block.header))
    block_to_hash_key = SchemaV1.make_block_hash_to_score_lookup_key(block.hash)
    assert not chaindb.exists(block_to_hash_key)
    chaindb.persist_block(block)
    assert chaindb.exists(block_to_hash_key)


def test_chaindb_get_score(chaindb):
    genesis = BlockHeader(difficulty=1, block_number=0, gas_limit=0)
    chaindb.persist_header(genesis)

    genesis_score_key = SchemaV1.make_block_hash_to_score_lookup_key(genesis.hash)
    genesis_score = rlp.decode(
        chaindb.db.get(genesis_score_key), sedes=rlp.sedes.big_endian_int
    )
    assert genesis_score == 1
    assert chaindb.get_score(genesis.hash) == 1

    block1 = BlockHeader(
        difficulty=10,
        block_number=1,
        gas_limit=0,
        parent_hash=genesis.hash,
        timestamp=genesis.timestamp + 1,
    )
    chaindb.persist_header(block1)

    block1_score_key = SchemaV1.make_block_hash_to_score_lookup_key(block1.hash)
    block1_score = rlp.decode(
        chaindb.db.get(block1_score_key), sedes=rlp.sedes.big_endian_int
    )
    assert block1_score == 11
    assert chaindb.get_score(block1.hash) == 11


def test_chaindb_get_block_header_by_hash(chaindb, block, header):
    block = block.copy(header=set_empty_root(chaindb, block.header))
    header = set_empty_root(chaindb, header)
    chaindb.persist_block(block)
    block_header = chaindb.get_block_header_by_hash(block.hash)
    assert_headers_eq(block_header, header)


def test_chaindb_get_canonical_block_hash(chaindb, block):
    block = block.copy(header=set_empty_root(chaindb, block.header))
    chaindb.persist_block(block)
    block_hash = chaindb.get_canonical_block_hash(block.number)
    assert block_hash == block.hash


def mine_blocks_with_receipts(
    chain, num_blocks, num_tx_per_block, funded_address, funded_address_private_key
):
    for _ in range(num_blocks):
        block_receipts = []
        for _ in range(num_tx_per_block):
            tx = new_transaction(
                chain.get_vm(),
                from_=funded_address,
                to=force_bytes_to_address(b"\x10\x10"),
                private_key=funded_address_private_key,
            )
            new_block, tx_receipt, computation = chain.apply_transaction(tx)
            block_receipts.append(tx_receipt)
            computation.raise_if_error()

        yield chain.mine_block(), block_receipts


def test_chaindb_get_receipt_and_tx_by_index(
    chain, funded_address, funded_address_private_key
):
    NUMBER_BLOCKS_IN_CHAIN = 5
    TRANSACTIONS_IN_BLOCK = 10
    REQUIRED_BLOCK_NUMBER = 2
    REQUIRED_RECEIPT_INDEX = 3

    for block, receipts in mine_blocks_with_receipts(
        chain,
        NUMBER_BLOCKS_IN_CHAIN,
        TRANSACTIONS_IN_BLOCK,
        funded_address,
        funded_address_private_key,
    ):
        if block.header.block_number == REQUIRED_BLOCK_NUMBER:
            actual_receipt = receipts[REQUIRED_RECEIPT_INDEX]
            actual_tx = block.transactions[REQUIRED_RECEIPT_INDEX]
            tx_class = block.transaction_builder

    receipt_builder = chain.get_vm().get_receipt_builder()

    # Check that the receipt retrieved is indeed the actual one
    chaindb_retrieved_receipt = chain.chaindb.get_receipt_by_index(
        REQUIRED_BLOCK_NUMBER,
        REQUIRED_RECEIPT_INDEX,
        receipt_builder,
    )
    assert chaindb_retrieved_receipt == actual_receipt

    chaindb_retrieved_tx = chain.chaindb.get_transaction_by_index(
        REQUIRED_BLOCK_NUMBER, REQUIRED_RECEIPT_INDEX, tx_class
    )
    assert chaindb_retrieved_tx == actual_tx

    # Raise error if block number is not found
    with pytest.raises(ReceiptNotFound):
        chain.chaindb.get_receipt_by_index(
            NUMBER_BLOCKS_IN_CHAIN + 1,
            REQUIRED_RECEIPT_INDEX,
            receipt_builder,
        )

    # Raise error if receipt index is out of range
    with pytest.raises(ReceiptNotFound):
        chain.chaindb.get_receipt_by_index(
            NUMBER_BLOCKS_IN_CHAIN,
            TRANSACTIONS_IN_BLOCK + 1,
            receipt_builder,
        )


def mine_blocks_with_access_list_receipts(
    chain, num_blocks, num_tx_per_block, funded_address, funded_address_private_key
):
    current_vm = chain.get_vm()
    if not isinstance(current_vm, (BerlinVM, LondonVM)):
        pytest.skip("{current_vm} does not support typed transactions")

    for _ in range(num_blocks):
        block_receipts = []
        for _ in range(num_tx_per_block):
            tx = new_access_list_transaction(
                chain.get_vm(),
                from_=funded_address,
                to=force_bytes_to_address(b"\x10\x10"),
                private_key=funded_address_private_key,
            )
            new_block, tx_receipt, computation = chain.apply_transaction(tx)
            block_receipts.append(tx_receipt)
            computation.raise_if_error()

        yield chain.mine_block(), block_receipts


def test_chaindb_get_access_list_receipt_and_tx_by_index(
    chain, funded_address, funded_address_private_key
):
    NUMBER_BLOCKS_IN_CHAIN = 5
    TRANSACTIONS_IN_BLOCK = 10
    REQUIRED_BLOCK_NUMBER = 2
    REQUIRED_RECEIPT_INDEX = 3

    for block, receipts in mine_blocks_with_access_list_receipts(
        chain,
        NUMBER_BLOCKS_IN_CHAIN,
        TRANSACTIONS_IN_BLOCK,
        funded_address,
        funded_address_private_key,
    ):
        if block.header.block_number == REQUIRED_BLOCK_NUMBER:
            actual_receipt = receipts[REQUIRED_RECEIPT_INDEX]
            actual_tx = block.transactions[REQUIRED_RECEIPT_INDEX]
            tx_class = block.transaction_builder

    receipt_builder = chain.get_vm().get_receipt_builder()

    # Check that the receipt retrieved is indeed the actual one
    chaindb_retrieved_receipt = chain.chaindb.get_receipt_by_index(
        REQUIRED_BLOCK_NUMBER,
        REQUIRED_RECEIPT_INDEX,
        receipt_builder,
    )
    assert chaindb_retrieved_receipt == actual_receipt

    chaindb_retrieved_tx = chain.chaindb.get_transaction_by_index(
        REQUIRED_BLOCK_NUMBER, REQUIRED_RECEIPT_INDEX, tx_class
    )
    assert chaindb_retrieved_tx == actual_tx

    # Raise error if block number is not found
    with pytest.raises(ReceiptNotFound):
        chain.chaindb.get_receipt_by_index(
            NUMBER_BLOCKS_IN_CHAIN + 1,
            REQUIRED_RECEIPT_INDEX,
            receipt_builder,
        )

    # Raise error if receipt index is out of range
    with pytest.raises(ReceiptNotFound):
        chain.chaindb.get_receipt_by_index(
            NUMBER_BLOCKS_IN_CHAIN,
            TRANSACTIONS_IN_BLOCK + 1,
            receipt_builder,
        )


@pytest.mark.parametrize(
    "use_persist_unexecuted_block",
    (
        True,
        pytest.param(
            False,
            marks=pytest.mark.xfail(
                reason=(
                    "The `persist_block` API relies on block execution to persist"
                    "transactions and receipts. It is expected to fail this test."
                )
            ),
        ),
    ),
)
def test_chaindb_persist_unexecuted_block(
    chain,
    chain_without_block_validation_factory,
    funded_address,
    funded_address_private_key,
    use_persist_unexecuted_block,
):
    # We need one chain to create blocks and a second one with a pristine database to
    # test persisting blocks that have not been executed.
    second_chain = chain_without_block_validation_factory(AtomicDB())
    assert chain.get_canonical_head() == second_chain.get_canonical_head()
    assert chain != second_chain

    NUMBER_BLOCKS_IN_CHAIN = 5
    TRANSACTIONS_IN_BLOCK = 10
    REQUIRED_BLOCK_NUMBER = 2
    REQUIRED_RECEIPT_INDEX = 3

    for block, receipts in mine_blocks_with_receipts(
        chain,
        NUMBER_BLOCKS_IN_CHAIN,
        TRANSACTIONS_IN_BLOCK,
        funded_address,
        funded_address_private_key,
    ):
        if block.header.block_number == REQUIRED_BLOCK_NUMBER:
            actual_receipt = receipts[REQUIRED_RECEIPT_INDEX]
            actual_tx = block.transactions[REQUIRED_RECEIPT_INDEX]
            tx_class = block.transaction_builder

        if use_persist_unexecuted_block:
            second_chain.chaindb.persist_unexecuted_block(block, receipts)
        else:
            # We just use this for an XFAIL to prove `persist_block` does not properly
            # persist blocks that were not executed.
            second_chain.chaindb.persist_block(block)

    chaindb_retrieved_tx = second_chain.chaindb.get_transaction_by_index(
        REQUIRED_BLOCK_NUMBER, REQUIRED_RECEIPT_INDEX, tx_class
    )
    assert chaindb_retrieved_tx == actual_tx

    receipt_builder = chain.get_vm().get_receipt_builder()

    # Check that the receipt retrieved is indeed the actual one
    chaindb_retrieved_receipt = second_chain.chaindb.get_receipt_by_index(
        REQUIRED_BLOCK_NUMBER,
        REQUIRED_RECEIPT_INDEX,
        receipt_builder,
    )
    assert chaindb_retrieved_receipt == actual_receipt

    # Raise error if block number is not found
    with pytest.raises(ReceiptNotFound):
        second_chain.chaindb.get_receipt_by_index(
            NUMBER_BLOCKS_IN_CHAIN + 1,
            REQUIRED_RECEIPT_INDEX,
            receipt_builder,
        )

    # Raise error if receipt index is out of range
    with pytest.raises(ReceiptNotFound):
        second_chain.chaindb.get_receipt_by_index(
            NUMBER_BLOCKS_IN_CHAIN,
            TRANSACTIONS_IN_BLOCK + 1,
            receipt_builder,
        )


def test_chaindb_raises_blocknotfound_on_missing_uncles(VM, chaindb, header):
    bad_header = header.copy(uncles_hash=b"unicorns" * 4)
    chaindb.persist_header(bad_header)

    with pytest.raises(BlockNotFound):
        VM.get_block_class().from_header(bad_header, chaindb)


def test_chaindb_raises_blocknotfound_on_missing_transactions(VM, chaindb, header):
    bad_header = header.copy(transaction_root=b"unicorns" * 4)
    chaindb.persist_header(bad_header)

    with pytest.raises(BlockNotFound):
        VM.get_block_class().from_header(bad_header, chaindb)
