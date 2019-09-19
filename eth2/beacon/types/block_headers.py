from eth.constants import ZERO_HASH32
from eth_typing import BLSSignature, Hash32
from eth_utils import humanize_hash
import ssz
from ssz.sedes import bytes32, bytes96, uint64

from eth2.beacon.constants import EMPTY_SIGNATURE, ZERO_SIGNING_ROOT
from eth2.beacon.typing import SigningRoot, Slot

from .defaults import default_slot


class BeaconBlockHeader(ssz.SignedSerializable):

    fields = [
        ("slot", uint64),
        ("parent_root", bytes32),
        ("state_root", bytes32),
        ("body_root", bytes32),
        ("signature", bytes96),
    ]

    def __init__(
        self,
        *,
        slot: Slot = default_slot,
        parent_root: SigningRoot = ZERO_SIGNING_ROOT,
        state_root: Hash32 = ZERO_HASH32,
        body_root: Hash32 = ZERO_HASH32,
        signature: BLSSignature = EMPTY_SIGNATURE,
    ):
        super().__init__(
            slot=slot,
            parent_root=parent_root,
            state_root=state_root,
            body_root=body_root,
            signature=signature,
        )

    def __str__(self) -> str:
        return (
            f"[signing_root]={humanize_hash(self.signing_root)},"
            f" [hash_tree_root]={humanize_hash(self.hash_tree_root)},"
            f" slot={self.slot},"
            f" parent_root={humanize_hash(self.parent_root)},"
            f" state_root={humanize_hash(self.state_root)},"
            f" body_root={humanize_hash(self.body_root)},"
            f" signature={humanize_hash(self.signature)}"
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {str(self)}>"


default_beacon_block_header = BeaconBlockHeader()
