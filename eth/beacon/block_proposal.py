from typing import (
    NamedTuple,
    TYPE_CHECKING,
)

from eth.constants import (
    Hash32,
)

if TYPE_CHECKING:
    from eth.beacon.types.blocks import AttestationRecord  # noqa: F401
    from eth.beacon.types.blocks import BaseBeaconBlock  # noqa: F401


BlockProposal = NamedTuple(
    'BlockProposal',
    (
        ('block', 'BaseBeaconBlock'),
        ('shard_id', int),
        ('shard_block_hash', Hash32),
    )
)
