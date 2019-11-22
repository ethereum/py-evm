from typing import Iterator, Sequence, Tuple

from eth_typing import BLSPubkey, BLSSignature, Hash32
from eth_utils import to_tuple
from milagro_bls_binding import (
    aggregate_pubkeys,
    aggregate_signatures,
    privtopub,
    sign,
    verify,
    verify_multiple,
)
from py_ecc.bls.typing import Domain

from eth2._utils.bls.backends.base import BaseBLSBackend
from eth2.beacon.constants import EMPTY_PUBKEY, EMPTY_SIGNATURE


def to_int(domain: Domain) -> int:
    """
    Convert Domain to big endian int since
    sigp/milagro_bls use big endian int on hash to g2.
    """
    return int.from_bytes(domain, "big")


@to_tuple
def filter_non_empty_pair(
    pubkeys: Sequence[BLSPubkey], message_hashes: Sequence[Hash32]
) -> Iterator[Tuple[BLSPubkey, Hash32]]:
    for i, pubkey in enumerate(pubkeys):
        if pubkey != EMPTY_PUBKEY:
            yield pubkey, message_hashes[i]


class MilagroBackend(BaseBLSBackend):
    @staticmethod
    def privtopub(k: int) -> BLSPubkey:
        return privtopub(k.to_bytes(48, "big"))

    @staticmethod
    def sign(message_hash: Hash32, privkey: int, domain: Domain) -> BLSSignature:
        return sign(message_hash, privkey.to_bytes(48, "big"), to_int(domain))

    @staticmethod
    def verify(
        message_hash: Hash32, pubkey: BLSPubkey, signature: BLSSignature, domain: Domain
    ) -> bool:
        if pubkey == EMPTY_PUBKEY:
            raise ValueError(
                f"Empty public key breaks Milagro binding  pubkey={pubkey.hex()}"
            )
        return verify(message_hash, pubkey, signature, to_int(domain))

    @staticmethod
    def aggregate_signatures(signatures: Sequence[BLSSignature]) -> BLSSignature:
        non_empty_signatures = tuple(
            sig for sig in signatures if sig != EMPTY_SIGNATURE
        )
        if len(non_empty_signatures) == 0:
            return EMPTY_SIGNATURE
        return aggregate_signatures(list(non_empty_signatures))

    @staticmethod
    def aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
        non_empty_pubkeys = tuple(key for key in pubkeys if key != EMPTY_PUBKEY)
        if len(non_empty_pubkeys) == 0:
            return EMPTY_PUBKEY
        return aggregate_pubkeys(list(non_empty_pubkeys))

    @staticmethod
    def verify_multiple(
        pubkeys: Sequence[BLSPubkey],
        message_hashes: Sequence[Hash32],
        signature: BLSSignature,
        domain: Domain,
    ) -> bool:
        if signature == EMPTY_SIGNATURE:
            raise ValueError(
                f"Empty signature breaks Milagro binding  signature={signature.hex()}"
            )

        non_empty_pubkeys, filtered_message_hashes = zip(
            *filter_non_empty_pair(pubkeys, message_hashes)
        )

        return verify_multiple(
            list(non_empty_pubkeys),
            list(filtered_message_hashes),
            signature,
            to_int(domain),
        )
