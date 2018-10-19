import pytest
import rlp

from eth_utils import decode_hex

from eth.beacon.state_machines.forks.serenity.blocks import SerenityBeaconBlock


@pytest.fixture
def chain(beacon_chain_without_block_validation):
    return beacon_chain_without_block_validation


@pytest.fixture
def valid_chain(beacon_chain_with_block_validation):
    return beacon_chain_with_block_validation


# The valid block RLP data under parameter:
# num_validators=1000
# cycle_length=20
# min_committee_size=10
# shard_count=100
valid_block_rlp = decode_hex(
    "0x"
    "f8e8a0f6ccfe9efcfdc7915ae1c81bf19a353886bd06a749e3ccba4177d8619c"
    "48a27fb840000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000001a00000000000000000000000000000000000000000000000000000"
    "000000000000c0a0000000000000000000000000000000000000000000000000"
    "0000000000000000a00610b46e7e3ffcb11843b7831e439954edf7a8ee6a1e70"
    "c1cea6a86c4808d522a0f8d6d603f8d7757411700348390fcb5ff2ca9f0b6af7"
    "89c30bb23a4e8482445a"
)


@pytest.mark.parametrize(
    (
        'num_validators,cycle_length,min_committee_size,shard_count'
    ),
    [
        (1000, 20, 10, 100),
    ]
)
def test_import_block_validation(valid_chain):
    block = rlp.decode(valid_block_rlp, sedes=SerenityBeaconBlock)
    imported_block, _, _ = valid_chain.import_block(block)
    assert imported_block == block


@pytest.mark.parametrize(
    (
        'num_validators,cycle_length,min_committee_size,shard_count'
    ),
    [
        (1000, 20, 10, 100),
    ]
)
def test_canonical_chain(valid_chain):
    genesis_block = valid_chain.chaindb.get_canonical_block_by_slot(0)

    # Our chain fixture is created with only the genesis header, so initially that's the head of
    # the canonical chain.
    assert valid_chain.get_canonical_head() == genesis_block

    block = rlp.decode(valid_block_rlp, sedes=SerenityBeaconBlock)
    valid_chain.chaindb.persist_block(block)

    assert valid_chain.get_canonical_head() == block

    canonical_block_1 = valid_chain.chaindb.get_canonical_block_by_slot(
        genesis_block.slot_number + 1)
    assert canonical_block_1 == block
