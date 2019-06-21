from typing import (
    cast,
    NamedTuple,
    Tuple,
    Union,
)

import rlp
from rlp.exceptions import (
    DecodingError,
)

from eth_utils import (
    is_bytes,
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
    validate_nonce,
    Nonce,
)
from p2p.discv5.constants import (
    AUTH_SCHEME_NAME,
    MAX_PACKET_SIZE,
    TAG_SIZE,
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

    def to_wire_bytes(self) -> bytes:
        encoded_packet = b"".join((
            self.tag,
            rlp.encode(self.auth_tag),
            self.encrypted_message,
        ))
        validate_max_packet_size(encoded_packet)
        return encoded_packet


#
# Validation
#
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
