from eth_typing import BLSPubkey, BLSSignature
from eth_utils import humanize_hash
import ssz
from ssz.sedes import bytes48, bytes96, uint64

from eth2.beacon.constants import EMPTY_SIGNATURE
from eth2.beacon.typing import Gwei, Slot, ValidatorIndex

from .defaults import (
    default_bls_pubkey,
    default_gwei,
    default_slot,
    default_validator_index,
)


class Transfer(ssz.SignedSerializable):
    fields = [
        ("sender", uint64),
        ("recipient", uint64),
        ("amount", uint64),
        ("fee", uint64),
        # Inclusion slot
        ("slot", uint64),
        # Sender withdrawal pubkey
        ("pubkey", bytes48),
        # Sender signature
        ("signature", bytes96),
    ]

    def __init__(
        self,
        sender: ValidatorIndex = default_validator_index,
        recipient: ValidatorIndex = default_validator_index,
        amount: Gwei = default_gwei,
        fee: Gwei = default_gwei,
        slot: Slot = default_slot,
        pubkey: BLSPubkey = default_bls_pubkey,
        signature: BLSSignature = EMPTY_SIGNATURE,
    ) -> None:
        super().__init__(
            sender=sender,
            recipient=recipient,
            amount=amount,
            fee=fee,
            slot=slot,
            pubkey=pubkey,
            signature=signature,
        )

    def __str__(self) -> str:
        return (
            f"[signing_root]={humanize_hash(self.signing_root)},"
            f" [hash_tree_root]={humanize_hash(self.hash_tree_root)},"
            f" sender={self.sender},"
            f" recipient={self.recipient},"
            f" amount={self.amount},"
            f" fee={self.fee},"
            f" slot={self.slot},"
            f" pubkey={humanize_hash(self.pubkey)},"
            f" signature={humanize_hash(self.signature)}"
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {str(self)}>"
