from eth.beacon.types.validator_record import (
    ValidatorRecord,
)
from eth.constants import (
    ZERO_HASH32,
)


def mock_validator_record(pubkey, beacon_config, start_dynasty=0):
    return ValidatorRecord(
        pubkey=pubkey,
        withdrawal_shard=0,
        withdrawal_address=pubkey.to_bytes(32, 'big')[-20:],
        randao_commitment=b'\x55' * 32,
        balance=beacon_config.deposit_size,
        start_dynasty=start_dynasty,
        end_dynasty=beacon_config.default_end_dynasty
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
