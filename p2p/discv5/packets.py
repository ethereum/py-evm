import hashlib
import secrets

from typing import (
    cast,
    Callable,
    NamedTuple,
    Optional,
    Tuple,
    Union,
)

import rlp
from rlp.sedes import (
    big_endian_int,
)
from rlp.codec import (
    consume_length_prefix,
)
from rlp.exceptions import (
    DecodingError,
    DeserializationError,
)

from eth_utils import (
    big_endian_to_int,
    encode_hex,
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
    aesgcm_decrypt,
    aesgcm_encrypt,
    validate_nonce,
)
from p2p.discv5.messages import (
    BaseMessage,
    MessageTypeRegistry,
    default_message_type_registry,
)
from p2p.discv5.enr import (
    ENR,
)
from p2p.discv5.constants import (
    AUTH_RESPONSE_VERSION,
    AUTH_SCHEME_NAME,
    ID_NONCE_SIZE,
    MAX_PACKET_SIZE,
    NONCE_SIZE,
    RANDOM_ENCRYPTED_DATA_SIZE,
    TAG_SIZE,
    MAGIC_SIZE,
    ZERO_NONCE,
    WHO_ARE_YOU_MAGIC_SUFFIX,
)
from p2p.discv5.typing import (
    AES128Key,
    IDNonce,
    NodeID,
    Nonce,
    Tag,
)


#
# Packet data structures
#
class AuthHeader(NamedTuple):
    auth_tag: Nonce
    id_nonce: IDNonce
    auth_scheme_name: bytes
    ephemeral_public_key: bytes
    encrypted_auth_response: bytes


class AuthHeaderPacket(NamedTuple):
    tag: Tag
    auth_header: AuthHeader
    encrypted_message: bytes

    @classmethod
    def prepare(cls,
                *,
                tag: Tag,
                auth_tag: Nonce,
                id_nonce: IDNonce,
                message: BaseMessage,
                initiator_key: AES128Key,
                id_nonce_signature: bytes,
                auth_response_key: AES128Key,
                enr: Optional[ENR],
                ephemeral_public_key: bytes,
                ) -> "AuthHeaderPacket":
        encrypted_auth_response = compute_encrypted_auth_response(
            auth_response_key=auth_response_key,
            id_nonce_signature=id_nonce_signature,
            enr=enr,
        )
        auth_header = AuthHeader(
            auth_tag=auth_tag,
            id_nonce=id_nonce,
            auth_scheme_name=AUTH_SCHEME_NAME,
            ephemeral_public_key=ephemeral_public_key,
            encrypted_auth_response=encrypted_auth_response,
        )

        authenticated_data = b"".join((
            tag,
            rlp.encode(auth_header),
        ))
        encrypted_message = compute_encrypted_message(
            key=initiator_key,
            auth_tag=auth_tag,
            message=message,
            authenticated_data=authenticated_data,
        )

        return cls(
            tag=tag,
            auth_header=auth_header,
            encrypted_message=encrypted_message,
        )

    def decrypt_auth_response(self, auth_response_key: AES128Key) -> Tuple[bytes, Optional[ENR]]:
        """Extract id nonce signature and optional ENR from auth header packet."""
        plain_text = aesgcm_decrypt(
            key=auth_response_key,
            nonce=ZERO_NONCE,
            cipher_text=self.auth_header.encrypted_auth_response,
            authenticated_data=b"",
        )

        try:
            decoded_rlp = rlp.decode(plain_text)
        except DecodingError as error:
            raise ValidationError(
                f"Auth response does not contain valid RLP: {encode_hex(plain_text)}"
            )

        if not is_list_like(decoded_rlp):
            raise ValidationError(
                f"Auth response contains bytes instead of list: {encode_hex(decoded_rlp)}"
            )

        if len(decoded_rlp) != 3:
            raise ValidationError(
                f"Auth response is a list of {len(decoded_rlp)} instead of three elements"
            )
        version_bytes, id_nonce_signature, serialized_enr = decoded_rlp

        if not is_bytes(version_bytes):
            raise ValidationError(
                f"Version is a list instead of big endian encoded integer: {version_bytes}"
            )
        version_int = big_endian_to_int(version_bytes)
        if version_int != AUTH_RESPONSE_VERSION:
            raise ValidationError(
                f"Expected auth response version {AUTH_RESPONSE_VERSION}, but got {version_int}"
            )

        if not is_bytes(id_nonce_signature):
            raise ValidationError(
                f"Id nonce signature is a list instead of bytes: {id_nonce_signature}"
            )

        if not is_list_like(serialized_enr):
            raise ValidationError(f"ENR is bytes instead of list: {encode_hex(serialized_enr)}")

        if len(serialized_enr) == 0:
            enr = None
        else:
            try:
                enr = ENR.deserialize(serialized_enr)
            except DeserializationError as error:
                raise ValidationError("ENR in auth response is not properly encoded") from error

        return id_nonce_signature, enr

    def decrypt_message(self,
                        key: AES128Key,
                        message_type_registry: MessageTypeRegistry = default_message_type_registry,
                        ) -> BaseMessage:
        return _decrypt_message(
            key=key,
            auth_tag=self.auth_header.auth_tag,
            encrypted_message=self.encrypted_message,
            authenticated_data=self.tag + rlp.encode(self.auth_header),
            message_type_registry=message_type_registry,
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
    tag: Tag
    auth_tag: Nonce
    encrypted_message: bytes

    @classmethod
    def prepare(cls,
                *,
                tag: Tag,
                auth_tag: Nonce,
                message: BaseMessage,
                key: AES128Key,
                ) -> "AuthTagPacket":
        encrypted_message = compute_encrypted_message(
            key=key,
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
                       tag: Tag,
                       auth_tag: Nonce,
                       random_data: bytes,
                       ) -> "AuthTagPacket":
        return cls(
            tag=tag,
            auth_tag=auth_tag,
            encrypted_message=random_data,
        )

    def decrypt_message(self,
                        key: AES128Key,
                        message_type_registry: MessageTypeRegistry = default_message_type_registry,
                        ) -> BaseMessage:
        return _decrypt_message(
            key=key,
            auth_tag=self.auth_tag,
            encrypted_message=self.encrypted_message,
            authenticated_data=self.tag,
            message_type_registry=message_type_registry,
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
    magic: Hash32
    token: Nonce
    id_nonce: IDNonce
    enr_sequence_number: int

    @classmethod
    def prepare(cls,
                *,
                destination_node_id: NodeID,
                token: Nonce,
                id_nonce: IDNonce,
                enr_sequence_number: int,
                ) -> "WhoAreYouPacket":
        magic = compute_who_are_you_magic(destination_node_id)
        return cls(
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
            self.magic,
            message,
        ))

        validate_who_are_you_packet_size(encoded_packet)
        return encoded_packet


Packet = Union[WhoAreYouPacket, AuthHeaderPacket, AuthTagPacket]


#
# Validation
#
def validate_who_are_you_packet_size(encoded_packet: bytes) -> None:
    validate_max_packet_size(encoded_packet)
    if len(encoded_packet) < MAGIC_SIZE:
        raise ValidationError(
            f"Encoded packet is only {len(encoded_packet)} bytes, but should start with "
            f"{MAGIC_SIZE} bytes of magic"
        )
    if len(encoded_packet) - MAGIC_SIZE < 1:
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
    validate_length(auth_header.id_nonce, ID_NONCE_SIZE, "id nonce")


#
# Packet decoding
#
def get_packet_decoder(encoded_packet: bytes) -> Callable[[bytes], Packet]:
    # Both message and WhoAreYou packets start with 32 bytes (either magic or tag) followed by rlp
    # encoded data. Only in the case of message packets this is followed by the encrypted message.
    # Therefore, we distinguish the two by reading the RLP length prefix and then checking if there
    # is additional data.
    if MAGIC_SIZE != TAG_SIZE:
        raise Exception(
            "Invariant: This check works as magic and tag size are equal"
        )
    prefix_size = MAGIC_SIZE
    if len(encoded_packet) < prefix_size + 1:
        raise ValidationError(f"Packet is with {len(encoded_packet)} bytes too short")

    try:
        _, _, rlp_size, _ = consume_length_prefix(encoded_packet, MAGIC_SIZE)
    except DecodingError as error:
        raise ValidationError("RLP section of packet starts with invalid length prefix") from error

    expected_who_are_you_size = prefix_size + 1 + rlp_size
    if len(encoded_packet) > expected_who_are_you_size:
        return decode_message_packet
    elif len(encoded_packet) == expected_who_are_you_size:
        return decode_who_are_you_packet
    else:
        raise ValidationError("RLP section of packet is incomplete")


def decode_packet(encoded_packet: bytes) -> Packet:
    decoder = get_packet_decoder(encoded_packet)
    return decoder(encoded_packet)


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

    magic = _decode_who_are_you_magic(encoded_packet)
    token, id_nonce, enr_seq = _decode_who_are_you_payload(encoded_packet)
    return WhoAreYouPacket(
        magic=magic,
        token=token,
        id_nonce=id_nonce,
        enr_sequence_number=enr_seq,
    )


def _decode_tag(encoded_packet: bytes) -> Tag:
    return Tag(encoded_packet[:TAG_SIZE])


def _decode_auth(encoded_packet: bytes) -> Tuple[Union[AuthHeader, Nonce], int]:
    try:
        decoded_auth, _, message_start_index = rlp.codec.consume_item(encoded_packet, TAG_SIZE)
    except DecodingError as error:
        raise ValidationError("Packet authentication section is not proper RLP") from error

    if is_bytes(decoded_auth):
        validate_nonce(decoded_auth)
        return Nonce(decoded_auth), message_start_index
    elif is_list_like(decoded_auth):
        validate_length(decoded_auth, 5, "auth header")
        for index, element in enumerate(decoded_auth):
            if not is_bytes(element):
                raise ValidationError(f"Element {index} in auth header is not bytes: {element}")
        auth_header = AuthHeader(
            auth_tag=decoded_auth[0],
            id_nonce=decoded_auth[1],
            auth_scheme_name=decoded_auth[2],
            ephemeral_public_key=decoded_auth[3],
            encrypted_auth_response=decoded_auth[4],
        )
        validate_auth_header(auth_header)
        return auth_header, message_start_index
    else:
        raise Exception("unreachable: RLP can only encode bytes and lists")


def _decode_who_are_you_magic(encoded_packet: bytes) -> Hash32:
    return Hash32(encoded_packet[:MAGIC_SIZE])


def _decode_who_are_you_payload(encoded_packet: bytes) -> Tuple[Nonce, IDNonce, int]:
    payload_rlp = encoded_packet[MAGIC_SIZE:]

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
                                    ) -> bytes:
    if enr:
        plain_text_auth_response = rlp.encode([AUTH_RESPONSE_VERSION, id_nonce_signature, enr])
    else:
        plain_text_auth_response = rlp.encode([AUTH_RESPONSE_VERSION, id_nonce_signature, []])

    encrypted_auth_response = aesgcm_encrypt(
        key=auth_response_key,
        nonce=ZERO_NONCE,
        plain_text=plain_text_auth_response,
        authenticated_data=b"",
    )
    return encrypted_auth_response


def compute_encrypted_message(key: AES128Key,
                              auth_tag: Nonce,
                              message: BaseMessage,
                              authenticated_data: bytes,
                              ) -> bytes:
    encrypted_message = aesgcm_encrypt(
        key=key,
        nonce=auth_tag,
        plain_text=message.to_bytes(),
        authenticated_data=authenticated_data,
    )
    return encrypted_message


def compute_who_are_you_magic(destination_node_id: NodeID) -> Hash32:
    preimage = destination_node_id + WHO_ARE_YOU_MAGIC_SUFFIX
    return Hash32(hashlib.sha256(preimage).digest())


#
# Packet decryption
#
def _decrypt_message(key: AES128Key,
                     auth_tag: Nonce,
                     encrypted_message: bytes,
                     authenticated_data: bytes,
                     message_type_registry: MessageTypeRegistry,
                     ) -> BaseMessage:
    plain_text = aesgcm_decrypt(
        key=key,
        nonce=auth_tag,
        cipher_text=encrypted_message,
        authenticated_data=authenticated_data,
    )

    try:
        message_type = plain_text[0]
    except IndexError:
        raise ValidationError("Decrypted message is empty")

    try:
        message_class = message_type_registry[message_type]
    except KeyError:
        raise ValidationError(f"Unknown message type {message_type}")

    try:
        message = rlp.decode(plain_text[1:], message_class)
    except DecodingError as error:
        raise ValidationError("Encrypted message does not contain valid RLP") from error

    return message


#
# Random packet data
#
def get_random_encrypted_data() -> bytes:
    return secrets.token_bytes(RANDOM_ENCRYPTED_DATA_SIZE)


def get_random_id_nonce() -> IDNonce:
    return IDNonce(secrets.token_bytes(ID_NONCE_SIZE))


def get_random_auth_tag() -> Nonce:
    return Nonce(secrets.token_bytes(NONCE_SIZE))
