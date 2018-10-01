from eth.beacon.types.validator_record import (
    ValidatorRecord,
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
