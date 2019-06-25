"""
This module contains default values to be shared across types in the parent module.
"""

from eth_typing import (
    BLSPubkey,
)

from eth2.beacon.typing import (  # noqa: F401
    default_epoch,
    default_slot,
    default_shard,
    default_validator_index,
    default_gwei,
    default_timestamp,
    default_second,
    default_bitfield,
)

default_bls_pubkey = BLSPubkey(b'\x00' * 48)
default_tuple = tuple()
