from eth_utils import humanize_hash
import ssz
from ssz.sedes import bytes4, uint64

from eth2.beacon.typing import Epoch, Version

from .defaults import default_epoch, default_version


class Fork(ssz.Serializable):

    fields = [
        ("previous_version", bytes4),
        ("current_version", bytes4),
        # Epoch of latest fork
        ("epoch", uint64),
    ]

    def __init__(
        self,
        previous_version: Version = default_version,
        current_version: Version = default_version,
        epoch: Epoch = default_epoch,
    ) -> None:
        super().__init__(
            previous_version=previous_version,
            current_version=current_version,
            epoch=epoch,
        )

    def __str__(self) -> str:
        return (
            f"previous_version={humanize_hash(self.previous_version)},"
            f" current_version={humanize_hash(self.current_version)},"
            f" epoch={self.epoch}"
        )


default_fork = Fork()
