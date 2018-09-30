import pytest

from eth.beacon.types.attestation_record import (
    AttestationRecord,
)
from eth.constants import (
    ZERO_HASH32,
)


@pytest.mark.parametrize(
    'param,default_value',
    [
        ('slot', 0),
        ('shard_id', 0),
        ('oblique_parent_hashes', ()),
        ('shard_block_hash', ZERO_HASH32),
        ('attester_bitfield', b''),
        ('justified_slot', 0),
        ('justified_block_hash', ZERO_HASH32),
        ('aggregate_sig', (0, 0)),
    ]
)
def test_defaults(param, default_value, sample_attestation_record_params):
    del sample_attestation_record_params[param]
    attestation_record = AttestationRecord(**sample_attestation_record_params)

    assert getattr(attestation_record, param) == default_value
