from eth.beacon.enums import (
    ValidatorStatusCode,
)
from eth.beacon.types.validator_records import (
    ValidatorRecord,
)


def mock_validator_record(pubkey, max_deposit):
    return ValidatorRecord(
        pubkey=pubkey,
        withdrawal_credentials=b'\x44' * 32,
        randao_commitment=b'\x55' * 32,
        randao_skips=0,
        balance=max_deposit,
        status=ValidatorStatusCode.ACTIVE,
        latest_status_change_slot=0,
        exit_count=0,
    )


def get_pseudo_chain(length, genesis_block):
    """
    Get a pseudo chain, only slot and parent_hash are valid.
    """
    blocks = []
    ancestor_hashes_len = len(genesis_block.ancestor_hashes)
    for slot in range(length * 3):
        if slot > 0:
            ancestor_hashes = (
                (blocks[slot - 1].hash, ) +
                blocks[slot - 1].ancestor_hashes[:ancestor_hashes_len]
            )
        else:
            ancestor_hashes = genesis_block.ancestor_hashes
        blocks.append(
            genesis_block.copy(
                slot=slot,
                ancestor_hashes=ancestor_hashes
            )
        )

    return tuple(blocks)
