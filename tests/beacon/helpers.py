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
    Get a pseudo chain, only slot and parent_root are valid.
    """
    blocks = [genesis_block.copy()]
    for slot in range(1, length * 3):
        block = genesis_block.copy(
            slot=slot,
            parent_root=blocks[slot - 1].hash
        )

        blocks.append(block)

    return tuple(blocks)
