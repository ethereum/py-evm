from eth_typing import BLSSignature
from eth_utils import humanize_hash
import ssz
from ssz.sedes import bytes96, uint64

from eth2.beacon.constants import EMPTY_SIGNATURE
from eth2.beacon.typing import Epoch, ValidatorIndex

from .defaults import default_epoch, default_validator_index


class VoluntaryExit(ssz.SignedSerializable):

    fields = [
        # Minimum epoch for processing exit
        ("epoch", uint64),
        ("validator_index", uint64),
        ("signature", bytes96),
    ]

    def __init__(
        self,
        epoch: Epoch = default_epoch,
        validator_index: ValidatorIndex = default_validator_index,
        signature: BLSSignature = EMPTY_SIGNATURE,
    ) -> None:
        super().__init__(epoch, validator_index, signature)

    def __str__(self) -> str:
        return (
            f"epoch={self.epoch},"
            f" validator_index={self.validator_index},"
            f" signature={humanize_hash(self.signature)}"
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {str(self)}>"
