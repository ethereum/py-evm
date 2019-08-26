from typing import Sequence

from eth_typing import BLSPubkey
import ssz
from ssz.sedes import List, bytes48, uint64

from .defaults import default_tuple


class CompactCommittee(ssz.Serializable):

    fields = [("pubkeys", List(bytes48, 1)), ("compact_validators", List(uint64, 1))]

    def __init__(
        self,
        pubkeys: Sequence[BLSPubkey] = default_tuple,
        compact_validators: Sequence[int] = default_tuple,
    ) -> None:
        super().__init__(pubkeys=pubkeys, compact_validators=compact_validators)


default_compact_committee = CompactCommittee()
