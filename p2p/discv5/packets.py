import hashlib

from typing import (
    cast,
    NamedTuple,
    Optional,
    Tuple,
    Union,
)

import rlp
from rlp.sedes import (
    big_endian_int,
)
from rlp.exceptions import (
    DecodingError,
)

from eth_utils import (
    is_bytes,
    encode_hex,
    is_list_like,
    ValidationError,
)
from eth_typing import (
    Hash32,
)

from eth.validation import (
    validate_length,
    validate_length_lte,
)

from p2p.discv5.encryption import (
    aesgcm_encrypt,
    validate_nonce,
)
from p2p.discv5.messages import (
    BaseMessage,
)
from p2p.discv5.enr import (
    ENR,
)
from p2p.discv5.constants import (
    AUTH_SCHEME_NAME,
    MAX_PACKET_SIZE,
    TAG_SIZE,
    MAGIC_SIZE,
    ZERO_NONCE,
    WHO_ARE_YOU_MAGIC_SUFFIX,
)
from p2p.discv5.typing import (
    AES128Key,
    Nonce,
)


#
# Packet data structures
#
class AuthHeader(NamedTuple):
    auth_tag: Nonce
    auth_scheme_name: bytes
    ephemeral_pubkey: bytes
    encrypted_auth_response: bytes


class AuthHeaderPacket(NamedTuple):
    tag: Hash32
    auth_header: AuthHeader
    encrypted_message: bytes

    @classmethod
    def prepare(cls,
                *,
                tag: Hash32,
                auth_tag: Nonce,
                message: BaseMessage,
                initiator_key: AES128Key,
                id_nonce_signature: bytes,
                auth_response_key: AES128Key,
                enr: Optional[ENR],
                ephemeral_pubkey: bytes,
                ) -> "AuthHeaderPacket":
        encrypted_auth_response = compute_encrypted_auth_response(
            auth_response_key=auth_response_key,
            id_nonce_signature=id_nonce_signature,
            enr=enr,
            tag=tag,
        )
        auth_header = AuthHeader(
            auth_tag=auth_tag,
            auth_scheme_name=AUTH_SCHEME_NAME,
            ephemeral_pubkey=ephemeral_pubkey,
            encrypted_auth_response=encrypted_auth_response,
        )

        authenticated_data = b"".join((
            tag,
            rlp.encode(auth_header),
        ))
        encrypted_message = compute_encrypted_message(
            initiator_key=initiator_key,
            auth_tag=auth_tag,
            message=message,
            authenticated_data=authenticated_data,
        )

        return cls(
            tag=tag,
            auth_header=auth_header,
            encrypted_message=encrypted_message,
        )

    def to_wire_bytes(self) -> bytes:
        encoded_packet = b"".join((
            self.tag,
            rlp.encode(self.auth_header),
            self.encrypted_message,
        ))
        validate_max_packet_size(encoded_packet)
        return encoded_packet


class AuthTagPacket(NamedTuple):
    tag: Hash32
    auth_tag: Nonce
    encrypted_message: bytes

    @classmethod
    def prepare(cls,
                *,
                tag: Hash32,
                auth_tag: Nonce,
                message: BaseMessage,
                initiator_key: AES128Key,
                ) -> "AuthTagPacket":
        encrypted_message = compute_encrypted_message(
            initiator_key=initiator_key,
            auth_tag=auth_tag,
            message=message,
            authenticated_data=tag,
        )
        return cls(
            tag=tag,
            auth_tag=auth_tag,
            encrypted_message=encrypted_message,
        )

    @classmethod
    def prepare_random(cls,
                       *,
                       tag: Hash32,
                       auth_tag: Nonce,
                       random_data: bytes,
                       ) -> "AuthTagPacket":
        return cls(
            tag=tag,
            auth_tag=auth_tag,
            encrypted_message=random_data,
        )

    def to_wire_bytes(self) -> bytes:
        encoded_packet = b"".join((
            self.tag,
            rlp.encode(self.auth_tag),
            self.encrypted_message,
        ))
        validate_max_packet_size(encoded_packet)
        return encoded_packet


class WhoAreYouPacket(NamedTuple):
    tag: Hash32
    magic: Hash32
    token: Nonce
    id_nonce: bytes
    enr_sequence_number: int

    @classmethod
    def prepare(cls,
                *,
                tag: Hash32,
                destination_node_id: Hash32,
                token: Nonce,
                id_nonce: bytes,
                enr_sequence_number: int,
                ) -> "WhoAreYouPacket":
        magic = compute_who_are_you_magic(destination_node_id)
        return cls(
            tag=tag,
            magic=magic,
            token=token,
            id_nonce=id_nonce,
            enr_sequence_number=enr_sequence_number,
        )

    def to_wire_bytes(self) -> bytes:
        message = rlp.encode((
            self.token,
            self.id_nonce,
            self.enr_sequence_number,
        ))

        encoded_packet = b"".join((
            self.tag,
            self.magic,
            message,
        ))

        validate_who_are_you_packet_size(encoded_packet)
        return encoded_packet


#
# Validation
#
def validate_who_are_you_packet_size(encoded_packet: bytes) -> None:
    validate_max_packet_size(encoded_packet)
    validate_tag_prefix(encoded_packet)
    if len(encoded_packet) - TAG_SIZE < MAGIC_SIZE:
        raise ValidationError(
            f"Encoded packet is only {len(encoded_packet)} bytes, but should contain {MAGIC_SIZE} "
            f"bytes of magic following the {TAG_SIZE} tag at the beginning."
        )
    if len(encoded_packet) - TAG_SIZE - MAGIC_SIZE < 1:
        raise ValidationError(
            f"Encoded packet is missing RLP encoded payload section"
        )


def validate_message_packet_size(encoded_packet: bytes) -> None:
    validate_max_packet_size(encoded_packet)
    validate_tag_prefix(encoded_packet)
    if len(encoded_packet) - TAG_SIZE < 1:
        raise ValidationError(
            f"Message packet is missing RLP encoded auth section"
        )


def validate_max_packet_size(encoded_packet: bytes) -> None:
    validate_length_lte(encoded_packet, MAX_PACKET_SIZE, "packet")


def validate_tag_prefix(encoded_packet: bytes) -> None:
    if len(encoded_packet) < TAG_SIZE:
        raise ValidationError(
            f"Encoded packet is only {len(encoded_packet)} bytes, but should start with a "
            f"{TAG_SIZE} bytes tag"
        )


def validate_auth_header(auth_header: AuthHeader) -> None:
    validate_nonce(auth_header.auth_tag)
    if auth_header.auth_scheme_name != AUTH_SCHEME_NAME:
        raise ValidationError(
            f"Auth header uses scheme {auth_header.auth_scheme_name}, but only "
            f"{AUTH_SCHEME_NAME} is supported"
        )


#
# Packet decoding
#
def decode_message_packet(encoded_packet: bytes) -> Union[AuthTagPacket, AuthHeaderPacket]:
    validate_message_packet_size(encoded_packet)

    tag = _decode_tag(encoded_packet)
    auth, message_start_index = _decode_auth(encoded_packet)
    encrypted_message = encoded_packet[message_start_index:]

    packet: Union[AuthTagPacket, AuthHeaderPacket]
    if is_bytes(auth):
        packet = AuthTagPacket(
            tag=tag,
            auth_tag=cast(Nonce, auth),
            encrypted_message=encrypted_message,
        )
    elif isinstance(auth, AuthHeader):
        packet = AuthHeaderPacket(
            tag=tag,
            auth_header=auth,
            encrypted_message=encrypted_message,
        )
    else:
        raise Exception("Unreachable: decode_auth returns either Nonce or AuthHeader")

    return packet


def decode_who_are_you_packet(encoded_packet: bytes) -> WhoAreYouPacket:
    validate_who_are_you_packet_size(encoded_packet)

    tag = _decode_tag(encoded_packet)
    magic = _decode_who_are_you_magic(encoded_packet)
    token, id_nonce, enr_seq = _decode_who_are_you_payload(encoded_packet)
    return WhoAreYouPacket(
        tag=tag,
        magic=magic,
        token=token,
        id_nonce=id_nonce,
        enr_sequence_number=enr_seq,
    )


def _decode_tag(encoded_packet: bytes) -> Hash32:
    return Hash32(encoded_packet[:TAG_SIZE])


def _decode_auth(encoded_packet: bytes) -> Tuple[Union[AuthHeader, Nonce], int]:
    try:
        decoded_auth, _, message_start_index = rlp.codec.consume_item(encoded_packet, TAG_SIZE)
    except DecodingError as error:
        raise ValidationError("Packet authentication section is not proper RLP") from error

    if is_bytes(decoded_auth):
        validate_nonce(decoded_auth)
        return Nonce(decoded_auth), message_start_index
    elif is_list_like(decoded_auth):
        validate_length(decoded_auth, 4, "auth header")
        for index, element in enumerate(decoded_auth):
            if not is_bytes(element):
                raise ValidationError(f"Element {index} in auth header is not bytes: {element}")
        auth_header = AuthHeader(
            auth_tag=decoded_auth[0],
            auth_scheme_name=decoded_auth[1],
            ephemeral_pubkey=decoded_auth[2],
            encrypted_auth_response=decoded_auth[3],
        )
        validate_auth_header(auth_header)
        return auth_header, message_start_index
    else:
        raise Exception("unreachable: RLP can only encode bytes and lists")


def _decode_who_are_you_magic(encoded_packet: bytes) -> Hash32:
    return Hash32(encoded_packet[TAG_SIZE:TAG_SIZE + MAGIC_SIZE])


def _decode_who_are_you_payload(encoded_packet: bytes) -> Tuple[Nonce, bytes, int]:
    payload_rlp = encoded_packet[TAG_SIZE + MAGIC_SIZE:]

    try:
        payload = rlp.decode(payload_rlp)
    except DecodingError as error:
        raise ValidationError(
            f"WHOAREYOU payload section is not proper RLP: {encode_hex(payload_rlp)}"
        ) from error

    if not is_list_like(payload):
        raise ValidationError(
            f"WHOAREYOU payload section is not an RLP encoded list: {payload}"
        )
    if len(payload) != 3:
        raise ValidationError(
            f"WHOAREYOU payload consists of {len(payload)} instead of 3 elements: {payload}"
        )

    token, id_nonce, enr_seq_bytes = payload
    enr_seq = big_endian_int.deserialize(enr_seq_bytes)
    validate_nonce(token)
    return Nonce(token), id_nonce, enr_seq


#
# Packet data computation
#
def compute_encrypted_auth_response(auth_response_key: AES128Key,
                                    id_nonce_signature: bytes,
                                    enr: Optional[ENR],
                                    tag: Hash32,
                                    ) -> bytes:
    if enr:
        plain_text_auth_response = rlp.encode([id_nonce_signature, enr])
    else:
        plain_text_auth_response = rlp.encode([id_nonce_signature, []])

    encrypted_auth_response = aesgcm_encrypt(
        key=auth_response_key,
        nonce=ZERO_NONCE,
        plain_text=plain_text_auth_response,
        authenticated_data=tag,
    )
    return encrypted_auth_response


def compute_encrypted_message(initiator_key: AES128Key,
                              auth_tag: Nonce,
                              message: BaseMessage,
                              authenticated_data: bytes,
                              ) -> bytes:
    encrypted_message = aesgcm_encrypt(
        key=initiator_key,
        nonce=auth_tag,
        plain_text=message.to_bytes(),
        authenticated_data=authenticated_data,
    )
    return encrypted_message


def compute_who_are_you_magic(destination_node_id: Hash32) -> Hash32:
    preimage = destination_node_id + WHO_ARE_YOU_MAGIC_SUFFIX
    return Hash32(hashlib.sha256(preimage).digest())
