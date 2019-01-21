import pytest

from eth_utils import (
    ValidationError,
)

from trinity.protocol.bcc.validators import (
    BeaconBlocksValidator,
)

from .helpers import (
    create_test_block,
    create_branch,
)

TEST_BRANCH = create_branch(
    length=100,
    root=create_test_block(slot=9),
)


@pytest.mark.parametrize("block_slot_or_hash, max_blocks, result", [
    (10, 100, ()),
    (10, 100, TEST_BRANCH[:1]),
    (10, 100, TEST_BRANCH[:2]),
    (10, 100, TEST_BRANCH),


    (TEST_BRANCH[0].hash, 100, ()),
    (TEST_BRANCH[0].hash, 100, TEST_BRANCH[:1]),
    (TEST_BRANCH[0].hash, 100, TEST_BRANCH[:2]),
    (TEST_BRANCH[0].hash, 100, TEST_BRANCH),
])
def test_valid_beacon_blocks_validation(block_slot_or_hash, max_blocks, result):
    validator = BeaconBlocksValidator(10, 100)
    validator.validate_result(result)


@pytest.mark.parametrize("block_slot_or_hash, max_blocks, result", [
    (10, 100, TEST_BRANCH[1:]),
    (10, 100, TEST_BRANCH[::-1]),
    (10, 100, (TEST_BRANCH[0], TEST_BRANCH[2])),
    (10, 100, (TEST_BRANCH[0], TEST_BRANCH[2], TEST_BRANCH[1])),
    (10, 100, (TEST_BRANCH[0],) + TEST_BRANCH[1::-1]),
    (10, 99, TEST_BRANCH),
    (11, 100, TEST_BRANCH),
    (9, 100, TEST_BRANCH),

    (TEST_BRANCH[0].hash, 100, TEST_BRANCH[1:]),
    (TEST_BRANCH[0].hash, 100, TEST_BRANCH[::-1]),
    (TEST_BRANCH[0].hash, 100, (TEST_BRANCH[0], TEST_BRANCH[2])),
    (TEST_BRANCH[0].hash, 100, (TEST_BRANCH[0], TEST_BRANCH[2], TEST_BRANCH[1])),
    (TEST_BRANCH[0].hash, 100, (TEST_BRANCH[0],) + TEST_BRANCH[1::-1]),
    (TEST_BRANCH[0].hash, 99, TEST_BRANCH),
    (b"\x00" * 32, 100, TEST_BRANCH),
])
def test_invalid_beacon_blocks_validation(block_slot_or_hash, max_blocks, result):
    validator = BeaconBlocksValidator(block_slot_or_hash, max_blocks)
    with pytest.raises(ValidationError):
        validator.validate_result(result)
