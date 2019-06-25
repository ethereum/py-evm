"""
This module contains default values to be shared across types in the parent module.
"""
from typing import TYPE_CHECKING

from eth_typing import (
    BLSPubkey,
)

if TYPE_CHECKING:
    from typing import (  # noqa: F401
        Any,
        Tuple,
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

# NOTE: there is a bug in our current version of ``flake8`` (==3.5.0)
# which does not recognize the inline typing:
#     default_tuple: Tuple[Any, ...] = ...
# so we add the type via comment and do the ``TYPE_CHECKING`` dance above.
#
# for more info, see: https://stackoverflow.com/q/51885518
# updating to ``flake8==3.7.7`` fixes this bug but introduces many other breaking changes.
default_tuple = tuple()  # type: Tuple[Any, ...]
