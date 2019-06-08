from typing import (
    Sequence,
    cast,
)

import blspy as bls_chia

from eth_typing import (
    BLSPubkey,
    BLSSignature,
    Hash32,
)
from eth_utils import (
    ValidationError,
)


def _domain_to_bytes(domain: int) -> bytes:
    return domain.to_bytes(8, 'big')  # bytes8


def _privkey_int_to_bytes(privkey: int) -> bytes:
    # FIXME: workaround due to the privkey in Chia-Network BLS starts from 1
    return privkey.to_bytes(bls_chia.PrivateKey.PRIVATE_KEY_SIZE, "big")


def _hash_to_be_signed(message_hash: Hash32, domain: int) -> bytes:
    domain_in_bytes = _domain_to_bytes(domain)
    return message_hash + domain_in_bytes


def sign(message_hash: Hash32,
         privkey: int,
         domain: int) -> BLSSignature:
    privkey_chia = bls_chia.PrivateKey.from_bytes(_privkey_int_to_bytes(privkey))
    hash_to_be_signed = _hash_to_be_signed(message_hash, domain)
    sig_chia = privkey_chia.sign_insecure(hash_to_be_signed)
    sig_chia_bytes = sig_chia.serialize()
    return cast(BLSSignature, sig_chia_bytes)


def privtopub(k: int) -> BLSPubkey:
    privkey_chia = bls_chia.PrivateKey.from_bytes(_privkey_int_to_bytes(k))
    return cast(BLSPubkey, privkey_chia.get_public_key().serialize())


def verify(message_hash: Hash32, pubkey: BLSPubkey, signature: BLSSignature, domain: int) -> bool:
    hash_to_be_signed = _hash_to_be_signed(message_hash, domain)
    pubkey_chia = bls_chia.PublicKey.from_bytes(pubkey)
    signature_chia = bls_chia.Signature.from_bytes(signature)
    signature_chia.set_aggregation_info(
        bls_chia.AggregationInfo.from_msg(pubkey_chia, hash_to_be_signed)
    )
    return cast(bool, signature_chia.verify())


def aggregate_signatures(signatures: Sequence[BLSSignature]) -> BLSSignature:
    signatures_chia = [
        bls_chia.InsecureSignature.from_bytes(signature)
        for signature in signatures
    ]
    aggregated_signature = bls_chia.InsecureSignature.aggregate(signatures_chia)
    aggregated_signature_bytes = aggregated_signature.serialize()
    return cast(BLSSignature, aggregated_signature_bytes)


def aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
    pubkeys_chia = list(map(bls_chia.PublicKey.from_bytes, pubkeys))
    aggregated_pubkey_chia = bls_chia.PublicKey.aggregate_insecure(pubkeys_chia)
    return cast(BLSPubkey, aggregated_pubkey_chia.serialize())


def verify_multiple(pubkeys: Sequence[BLSPubkey],
                    message_hashes: Sequence[Hash32],
                    signature: BLSSignature,
                    domain: int) -> bool:

    len_msgs = len(message_hashes)

    if len(pubkeys) != len_msgs:
        raise ValidationError(
            "len(pubkeys) (%s) should be equal to len(message_hashes) (%s)" % (
                len(pubkeys), len_msgs
            )
        )

    message_hashes_with_domain = [
        _hash_to_be_signed(message_hash, domain)
        for message_hash in message_hashes
    ]
    pubkeys_chia = map(bls_chia.PublicKey.from_bytes, pubkeys)
    aggregate_infos = [
        bls_chia.AggregationInfo.from_msg(pubkey_chia, message_hash)
        for pubkey_chia, message_hash in zip(pubkeys_chia, message_hashes_with_domain)
    ]
    merged_info = bls_chia.AggregationInfo.merge_infos(aggregate_infos)

    signature_chia = bls_chia.Signature.from_bytes(signature)
    signature_chia.set_aggregation_info(merged_info)
    return cast(bool, signature_chia.verify())
