from eth_utils import encode_hex
import ssz
from ssz.sedes import bytes32, uint64

from eth2.beacon.constants import ZERO_SIGNING_ROOT
from eth2.beacon.typing import Epoch, SigningRoot

from .defaults import default_epoch


class Checkpoint(ssz.Serializable):

    fields = [("epoch", uint64), ("root", bytes32)]

    def __init__(
        self, epoch: Epoch = default_epoch, root: SigningRoot = ZERO_SIGNING_ROOT
    ) -> None:
        super().__init__(epoch=epoch, root=root)

    def __str__(self) -> str:
        return f"({self.epoch}, {encode_hex(self.root)[0:8]})"


default_checkpoint = Checkpoint()
