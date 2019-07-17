from typing import (
    Sequence,
    cast,
)

from blspy import (
    AggregationInfo,
    InsecureSignature,
    PrivateKey,
    PublicKey,
    Signature,
)
from eth_typing import (
    BLSPubkey,
    BLSSignature,
    Hash32,
)
from eth_utils import (
    ValidationError,
)

from eth2.beacon.constants import (
    EMPTY_PUBKEY,
    EMPTY_SIGNATURE,
)


def _privkey_from_int(privkey: int) -> PrivateKey:
    privkey_bytes = privkey.to_bytes(PrivateKey.PRIVATE_KEY_SIZE, "big")
    try:
        return PrivateKey.from_bytes(privkey_bytes)
    except RuntimeError as error:
        raise ValueError(f"Bad private key: {privkey}, {error}")


def _pubkey_from_bytes(pubkey: BLSPubkey) -> PublicKey:
    try:
        return PublicKey.from_bytes(pubkey)
    except (RuntimeError, ValueError) as error:
        raise ValidationError(f"Bad public key: {pubkey}, {error}")


def _signature_from_bytes(signature: BLSSignature) -> Signature:
    try:
        return Signature.from_bytes(signature)
    except (RuntimeError, ValueError) as error:
        raise ValidationError(f"Bad signature: {signature}, {error}")


def combine_domain(message_hash: Hash32, domain: int) -> bytes:
    return message_hash + domain.to_bytes(8, 'big')


def sign(message_hash: Hash32,
         privkey: int,
         domain: int) -> BLSSignature:
    privkey_chia = _privkey_from_int(privkey)
    sig_chia = privkey_chia.sign_insecure(
        combine_domain(message_hash, domain)
    )
    sig_chia_bytes = sig_chia.serialize()
    return cast(BLSSignature, sig_chia_bytes)


def privtopub(k: int) -> BLSPubkey:
    privkey_chia = _privkey_from_int(k)
    return cast(BLSPubkey, privkey_chia.get_public_key().serialize())


def verify(message_hash: Hash32, pubkey: BLSPubkey, signature: BLSSignature, domain: int) -> bool:
    pubkey_chia = _pubkey_from_bytes(pubkey)
    signature_chia = _signature_from_bytes(signature)
    signature_chia.set_aggregation_info(
        AggregationInfo.from_msg(
            pubkey_chia,
            combine_domain(message_hash, domain),
        )
    )
    return cast(bool, signature_chia.verify())


def aggregate_signatures(signatures: Sequence[BLSSignature]) -> BLSSignature:
    if len(signatures) == 0:
        return EMPTY_SIGNATURE

    signatures_chia = [
        InsecureSignature.from_bytes(signature)
        for signature in signatures
    ]
    aggregated_signature = InsecureSignature.aggregate(signatures_chia)
    aggregated_signature_bytes = aggregated_signature.serialize()
    return cast(BLSSignature, aggregated_signature_bytes)


def aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
    if len(pubkeys) == 0:
        return EMPTY_PUBKEY
    pubkeys_chia = [
        _pubkey_from_bytes(pubkey)
        for pubkey in pubkeys
    ]
    aggregated_pubkey_chia = PublicKey.aggregate_insecure(pubkeys_chia)
    return cast(BLSPubkey, aggregated_pubkey_chia.serialize())


def verify_multiple(pubkeys: Sequence[BLSPubkey],
                    message_hashes: Sequence[Hash32],
                    signature: BLSSignature,
                    domain: int) -> bool:
    len_msgs = len(message_hashes)
    len_pubkeys = len(pubkeys)

    if len_pubkeys != len_msgs:
        raise ValueError(
            "len(pubkeys) (%s) should be equal to len(message_hashes) (%s)" % (
                len_pubkeys, len_msgs
            )
        )

    message_hashes_with_domain = [
        combine_domain(message_hash, domain)
        for message_hash in message_hashes
    ]
    pubkeys_chia = map(_pubkey_from_bytes, pubkeys)
    aggregate_infos = [
        AggregationInfo.from_msg(pubkey_chia, message_hash)
        for pubkey_chia, message_hash in zip(pubkeys_chia, message_hashes_with_domain)
    ]
    merged_info = AggregationInfo.merge_infos(aggregate_infos)

    signature_chia = _signature_from_bytes(signature)
    signature_chia.set_aggregation_info(merged_info)
    return cast(bool, signature_chia.verify())
