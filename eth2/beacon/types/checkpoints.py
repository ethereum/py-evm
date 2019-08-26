from eth.constants import ZERO_HASH32
from eth_typing import Hash32
from eth_utils import encode_hex
import ssz
from ssz.sedes import bytes32, uint64

from eth2.beacon.typing import Epoch

from .defaults import default_epoch


class Checkpoint(ssz.Serializable):

    fields = [("epoch", uint64), ("root", bytes32)]

    def __init__(
        self, epoch: Epoch = default_epoch, root: Hash32 = ZERO_HASH32
    ) -> None:
        super().__init__(epoch=epoch, root=root)

    def __str__(self) -> str:
        return f"({self.epoch}, {encode_hex(self.root)[0:8]})"


default_checkpoint = Checkpoint()
