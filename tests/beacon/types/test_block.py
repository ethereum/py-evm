import pytest

import rlp

from eth.beacon.types.block import (
    Block,
)
from eth.beacon.types.attestation_record import (
    AttestationRecord,
)
from eth.constants import (
    ZERO_HASH32,
)
from eth.utils.blake import (
    blake,
)


@pytest.mark.parametrize(
    'param,default_value',
    [
        ('parent_hash', ZERO_HASH32),
        ('slot_number', 0),
        ('randao_reveal', ZERO_HASH32),
        ('attestations', ()),
        ('pow_chain_ref', ZERO_HASH32),
        ('active_state_root', ZERO_HASH32),
        ('crystallized_state_root', ZERO_HASH32),
    ]
)
def test_defaults(param, default_value, sample_block_params):
    del sample_block_params[param]
    block = Block(**sample_block_params)
    assert getattr(block, param) == default_value


def test_update_slot():
    block = Block()
    block = block.copy(slot_number=10)
    assert block.slot_number == 10


def test_update_attestations():
    block = Block()
    attestations = block.attestations
    attestations = list(attestations)
    attestations.append(AttestationRecord())
    block2 = block.copy(
        attestations=attestations
    )
    assert block2.num_attestations == 1


def test_hash():
    block = Block()
    assert block.hash == blake(rlp.encode(block))
