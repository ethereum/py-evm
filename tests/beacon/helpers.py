from eth.beacon.config import (
    DEFAULT_CONFIG,
)
from eth.beacon.types.validator_record import (
    ValidatorRecord,
)


def mock_validator_record(pubkey, start_dynasty=0, config=DEFAULT_CONFIG):
    return ValidatorRecord(
        pubkey=pubkey,
        withdrawal_shard=0,
        withdrawal_address=pubkey.to_bytes(32, 'big')[-20:],
        randao_commitment=b'\x55' * 32,
        balance=config['deposit_size'],
        start_dynasty=start_dynasty,
        end_dynasty=config['default_end_dynasty']
    )
