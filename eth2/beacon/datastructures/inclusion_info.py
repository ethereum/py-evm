from typing import (
    NamedTuple,
)

from eth2.beacon.typing import Slot


class InclusionInfo(NamedTuple):
    inclusion_slot: Slot
    attestation_from_slot: Slot

    @property
    def inclusion_distance(self) -> int:
        return self.inclusion_slot - self.attestation_from_slot
