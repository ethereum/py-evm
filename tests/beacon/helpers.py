from eth.beacon.enums.validator_status_codes import (
    ValidatorStatusCode,
)
from eth.beacon.types.validator_records import (
    ValidatorRecord,
)
from eth.constants import (
    ZERO_HASH32,
)


def mock_validator_record(pubkey, deposit_size):
    return ValidatorRecord(
        pubkey=pubkey,
        withdrawal_credentials=b'\x44' * 32,
        randao_commitment=b'\x55' * 32,
        randao_skips=0,
        balance=deposit_size,
        status=ValidatorStatusCode.ACTIVE,
        latest_status_change_slot=0,
        exit_count=0,
    )


def get_pseudo_chain(length, genesis_block):
    """Get a pseudo chain, only slot_number and parent_hash are valid.
    """
    blocks = []
    for slot in range(length * 3):
        blocks.append(
            genesis_block.copy(
                slot_number=slot,
                parent_hash=blocks[slot - 1].hash if slot > 0 else ZERO_HASH32
            )
        )

    return blocks
