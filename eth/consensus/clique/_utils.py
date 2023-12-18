from typing import (
    Iterable,
)

from eth_keys import (
    keys,
)
from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    ValidationError,
    encode_hex,
    to_tuple,
)

from eth._utils.headers import (
    eth_now,
)
from eth.abc import (
    BlockHeaderAPI,
)
from eth.constants import (
    EMPTY_UNCLE_HASH,
    ZERO_ADDRESS,
    ZERO_HASH32,
)

from .constants import (
    ALLOWED_CLIQUE_DIFFICULTIES,
    COMMON_ADDRESS_LENGTH,
    NONCE_AUTH,
    NONCE_DROP,
    SIGNATURE_LENGTH,
    VANITY_LENGTH,
)
from .datatypes import (
    Snapshot,
)


@to_tuple
def get_signers_at_checkpoint(header: BlockHeaderAPI) -> Iterable[Address]:
    """
    Read the list of signers from a checkpoint header.
    """
    signers_length = len(header.extra_data) - VANITY_LENGTH - SIGNATURE_LENGTH

    if signers_length % COMMON_ADDRESS_LENGTH != 0:
        raise ValidationError("Checkpoint header must contain list of signers")

    signer_count = int(
        (len(header.extra_data) - VANITY_LENGTH - SIGNATURE_LENGTH)
        / COMMON_ADDRESS_LENGTH
    )

    for i in range(signer_count):
        yield Address(
            header.extra_data[VANITY_LENGTH + i * COMMON_ADDRESS_LENGTH :][
                :COMMON_ADDRESS_LENGTH
            ]
        )


def get_signature_hash(header: BlockHeaderAPI) -> Hash32:
    """
    Return the hash that is signed by the block producer. It is defined as the hash of
    the ``header`` except that the last 65 bytes of the ``extra_data`` (the signature)
    are removed before calculating the hash.
    """
    if len(header.extra_data) < SIGNATURE_LENGTH:
        raise ValueError("header.extra_data too short to contain signature")

    signature_header: BlockHeaderAPI = header.copy(
        extra_data=header.extra_data[: len(header.extra_data) - SIGNATURE_LENGTH]
    )
    return signature_header.hash


def get_block_signer(header: BlockHeaderAPI) -> Address:
    """
    Return the address of the signer of the ``header``.
    """
    signature_hash = get_signature_hash(header)

    signature_bytes = header.extra_data[-SIGNATURE_LENGTH:]

    signature = keys.Signature(signature_bytes=signature_bytes)

    return signature.recover_public_key_from_msg_hash(
        signature_hash
    ).to_canonical_address()


def is_in_turn(signer: Address, snapshot: Snapshot, header: BlockHeaderAPI) -> bool:
    """
    Return ``True`` if the block was produced *in turn*, otherwise return ``False``.
    """
    sorted_signers = snapshot.get_sorted_signers()

    try:
        offset = sorted_signers.index(signer)
    except ValueError:
        return False
    else:
        return header.block_number % len(sorted_signers) == offset


def sign_block_header(
    header: BlockHeaderAPI, private_key: PrivateKey
) -> BlockHeaderAPI:
    signature_hash = get_signature_hash(header)
    signature = private_key.sign_msg_hash(signature_hash)
    signers = get_signers_at_checkpoint(header)

    signed_extra_data = b"".join(
        (
            header.extra_data[:VANITY_LENGTH],
            b"".join(signers),
            signature.to_bytes(),
        )
    )

    return header.copy(extra_data=signed_extra_data)


def is_checkpoint(block_number: int, epoch_length: int) -> bool:
    """
    Return ``True`` if the given ``block_number`` is a checkpoint, otherwise ``False``.
    """
    return block_number % epoch_length == 0


def validate_header_integrity(header: BlockHeaderAPI, epoch_length: int) -> None:
    if header.timestamp > eth_now():
        raise ValidationError(f"Invalid future timestamp: {header.timestamp}")

    at_checkpoint = is_checkpoint(header.block_number, epoch_length)

    if at_checkpoint and header.coinbase != ZERO_ADDRESS:
        raise ValidationError(
            f"Coinbase must be {encode_hex(ZERO_ADDRESS)} on checkpoints "
            f"but is {encode_hex(header.coinbase)}"
        )

    if header.nonce != NONCE_AUTH and header.nonce != NONCE_DROP:
        raise ValidationError(f"Invalid nonce: {header.nonce!r}")

    if at_checkpoint and header.nonce != NONCE_DROP:
        raise ValidationError(f"Invalid checkpoint nonce: {header.nonce!r}")

    if len(header.extra_data) < VANITY_LENGTH:
        raise ValidationError("Missing vanity bytes in extra data")

    if len(header.extra_data) < VANITY_LENGTH + SIGNATURE_LENGTH:
        raise ValidationError("Missing signature in extra_data")

    signers_length = len(header.extra_data) - VANITY_LENGTH - SIGNATURE_LENGTH

    if not at_checkpoint and signers_length != 0:
        raise ValidationError("Non-checkpoint header must not contain list of signers")

    if at_checkpoint and signers_length % COMMON_ADDRESS_LENGTH != 0:
        raise ValidationError("Checkpoint header must contain list of signers")

    if header.mix_hash != ZERO_HASH32:
        raise ValidationError(f"Invalid mix hash: {header.mix_hash!r}")

    if header.uncles_hash != EMPTY_UNCLE_HASH:
        raise ValidationError(f"Invalid uncle hash: {header.uncles_hash!r}")

    if header.difficulty not in ALLOWED_CLIQUE_DIFFICULTIES:
        raise ValidationError(f"Invalid difficulty: {header.difficulty}")
