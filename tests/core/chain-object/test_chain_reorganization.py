import pytest

from eth import constants
from eth.chains.base import MiningChain
from eth.chains.tester import MAINNET_VMS
from eth.db.backends.memory import MemoryDB


VM_CLASSES = tuple(
    VMClass
    for _, VMClass
    in MAINNET_VMS.items()
)


@pytest.fixture(params=VM_CLASSES)
def chain(request, genesis_state):
    VMClass = request.param.configure(validate_seal=lambda block: None)

    class ChainForTest(MiningChain):
        vm_configuration = ((0, VMClass),)
        network_id = 1337

    genesis_params = {
        'block_number': constants.GENESIS_BLOCK_NUMBER,
        'difficulty': constants.GENESIS_DIFFICULTY,
        'gas_limit': constants.GENESIS_GAS_LIMIT,
    }
    chain = ChainForTest.from_genesis(MemoryDB(), genesis_params, genesis_state)
    return chain


ZERO_ADDRESS = b'\x00' * 20


def test_import_block_with_reorg(chain, funded_address_private_key):
    # mine 3 "common blocks"
    block_0 = chain.get_canonical_block_by_number(0)
    assert block_0.number == 0
    block_1 = chain.mine_block()
    assert block_1.number == 1
    block_2 = chain.mine_block()
    assert block_2.number == 2
    block_3 = chain.mine_block()
    assert block_3.number == 3

    # make a duplicate chain with no shared state
    fork_db = MemoryDB(chain.chaindb.db.kv_store.copy())
    fork_chain = type(chain)(fork_db, chain.header)

    # sanity check to verify that the two chains are the same.
    assert chain.header == fork_chain.header

    assert chain.header.block_number == 4
    assert fork_chain.header.block_number == 4

    assert fork_chain.get_canonical_head() == chain.get_canonical_head()

    assert fork_chain.get_canonical_block_by_number(0) == block_0
    assert fork_chain.get_canonical_block_by_number(1) == block_1
    assert fork_chain.get_canonical_block_by_number(2) == block_2
    assert fork_chain.get_canonical_block_by_number(3) == block_3

    # now cause the fork chain to diverge from the main chain
    tx = fork_chain.create_unsigned_transaction(
        nonce=0,
        gas_price=1,
        gas=21000,
        to=ZERO_ADDRESS,
        value=0,
        data=b'',
    )
    fork_chain.apply_transaction(tx.as_signed_transaction(funded_address_private_key))

    # Mine 3 blocks, ensuring that the difficulty of the main chain remains
    # equal or greater than the fork chain
    block_4 = chain.mine_block()
    f_block_4 = fork_chain.mine_block()
    assert f_block_4 != block_4
    assert block_4.number == 4
    assert f_block_4.number == 4
    assert f_block_4.header.difficulty <= block_4.header.difficulty

    f_block_5, block_5 = fork_chain.mine_block(), chain.mine_block()
    assert f_block_5 != block_5
    assert block_5.number == 5
    assert f_block_5.number == 5
    assert f_block_5.header.difficulty <= block_5.header.difficulty

    f_block_6, block_6 = fork_chain.mine_block(), chain.mine_block()
    assert f_block_6 != block_6
    assert block_6.number == 6
    assert f_block_6.number == 6
    assert f_block_6.header.difficulty <= block_6.header.difficulty

    # now mine the 7th block which will outpace the main chain difficulty.
    f_block_7 = fork_chain.mine_block()

    pre_fork_chain_head = chain.header

    # now we proceed to import the blocks from the fork chain into the main
    # chain.  Blocks 4, 5, and 6 should import resulting in no re-organization.
    for block in (f_block_4, f_block_5, f_block_6):
        _, new_canonical_blocks, old_canonical_blocks = chain.import_block(block)
        assert not new_canonical_blocks
        assert not old_canonical_blocks
        assert chain.header == pre_fork_chain_head

    # now we import block 7 from the fork chain.  This should cause a re-org.
    _, new_canonical_blocks, old_canonical_blocks = chain.import_block(f_block_7)
    assert new_canonical_blocks == (f_block_4, f_block_5, f_block_6, f_block_7)
    assert old_canonical_blocks == (block_4, block_5, block_6)

    assert chain.get_canonical_head() == f_block_7.header
