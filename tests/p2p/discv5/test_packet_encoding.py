import pytest

from hypothesis import (
    given,
    strategies as st,
)

from eth_utils import (
    ValidationError,
)

import rlp

from p2p.discv5.packets import (
    AuthTagPacket,
    AuthHeaderPacket,
    WhoAreYouPacket,
    decode_message_packet,
    decode_packet,
    decode_who_are_you_packet,
)
from p2p.discv5.constants import (
    NONCE_SIZE,
    ID_NONCE_SIZE,
    TAG_SIZE,
    MAX_PACKET_SIZE,
    AUTH_SCHEME_NAME,
    MAGIC_SIZE,
)

from p2p.tools.factories import (
    AuthHeaderFactory,
    AuthHeaderPacketFactory,
    AuthTagPacketFactory,
    WhoAreYouPacketFactory,
)

from tests.p2p.discv5.strategies import (
    enr_seq_st,
    id_nonce_st,
    magic_st,
    nonce_st,
    tag_st,
)

# arbitrary as we're not working with a particular identity scheme
public_key_st = st.binary(min_size=33, max_size=33)


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    encrypted_message_size=st.integers(
        min_value=0,
        # account for RLP prefix of auth tag
        max_value=MAX_PACKET_SIZE - (1 + TAG_SIZE) - NONCE_SIZE,
    ),
)
def test_auth_tag_packet_encoding_decoding(tag, auth_tag, encrypted_message_size):
    encrypted_message = b"\x00" * encrypted_message_size
    original_packet = AuthTagPacketFactory(
        tag=tag,
        auth_tag=auth_tag,
        encrypted_message=encrypted_message,
    )
    encoded_packet = original_packet.to_wire_bytes()
    decoded_packet = decode_message_packet(encoded_packet)
    assert isinstance(decoded_packet, AuthTagPacket)
    assert decoded_packet == original_packet


def test_oversize_auth_tag_packet_encoding():
    packet = AuthTagPacketFactory(
        encrypted_message=b"\x00" * (MAX_PACKET_SIZE - (1 + TAG_SIZE) - NONCE_SIZE + 1),
    )
    with pytest.raises(ValidationError):
        packet.to_wire_bytes()


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    id_nonce=id_nonce_st,
    ephemeral_public_key=public_key_st,
    encrypted_auth_response=st.binary(min_size=16, max_size=32),
    encrypted_message_size=st.integers(
        min_value=0,
        # account for various RLP prefixes in auth header and assume max length for all entries
        max_value=MAX_PACKET_SIZE - TAG_SIZE - sum((
            2,  # rlp list prefix
            1 + NONCE_SIZE,  # tag
            1 + len(AUTH_SCHEME_NAME),  # auth scheme name
            1 + ID_NONCE_SIZE,  # id nonce
            1 + 33,  # public_key
            1 + 32,  # encrypted auth response
        ))
    ),
)
def test_auth_header_packet_encoding_decoding(tag,
                                              auth_tag,
                                              id_nonce,
                                              ephemeral_public_key,
                                              encrypted_auth_response,
                                              encrypted_message_size):
    auth_header = AuthHeaderFactory(
        auth_tag=auth_tag,
        id_nonce=id_nonce,
        ephemeral_public_key=ephemeral_public_key,
        encrypted_auth_response=encrypted_auth_response,
    )
    encrypted_message = b"\x00" * encrypted_message_size
    original_packet = AuthHeaderPacketFactory(
        tag=tag,
        auth_header=auth_header,
        encrypted_message=encrypted_message,
    )
    encoded_packet = original_packet.to_wire_bytes()
    decoded_packet = decode_message_packet(encoded_packet)
    assert isinstance(decoded_packet, AuthHeaderPacket)
    assert decoded_packet == original_packet


def test_oversize_auth_header_packet_encoding():
    auth_header = AuthHeaderFactory(encrypted_auth_response=32)
    header_size = len(rlp.encode(auth_header))
    encrypted_message_size = MAX_PACKET_SIZE - TAG_SIZE - header_size + 1
    encrypted_message = b"\x00" * encrypted_message_size
    packet = AuthHeaderPacketFactory(
        auth_header=auth_header,
        encrypted_message=encrypted_message,
    )
    with pytest.raises(ValidationError):
        packet.to_wire_bytes()


@pytest.mark.parametrize("encoded_packet", (
    b"",  # empty
    b"\x00" * TAG_SIZE,  # no auth section
    b"\x00" * 500,  # invalid RLP auth section
    # auth header with too few elements
    b"\x00" * TAG_SIZE + rlp.encode((
        b"\x00" * NONCE_SIZE,
        b"\x00" * ID_NONCE_SIZE,
        AUTH_SCHEME_NAME,
        b"",
    )),
    # auth header with too many elements
    b"\x00" * TAG_SIZE + rlp.encode((
        b"\x00" * NONCE_SIZE,
        b"\x00" * ID_NONCE_SIZE,
        AUTH_SCHEME_NAME,
        b"",
        b"",
        b"",
    )),
    # auth header with invalid tag
    b"\x00" * TAG_SIZE + rlp.encode((
        b"\x00" * (NONCE_SIZE - 1),
        b"\x00" * ID_NONCE_SIZE,
        AUTH_SCHEME_NAME,
        b"",
        b"",
    )),
    # auth header with invalid id nonce
    b"\x00" * TAG_SIZE + rlp.encode((
        b"\x00" * (NONCE_SIZE - 1),
        b"\x00" * (ID_NONCE_SIZE - 1),
        AUTH_SCHEME_NAME,
        b"",
        b"",
    )),
    # auth header with wrong auth scheme
    b"\x00" * TAG_SIZE + rlp.encode((
        b"\x00" * NONCE_SIZE,
        b"\x00" * ID_NONCE_SIZE,
        b"no-gcm",
        b"",
        b"",
    )),
    # auth header with tag being a list
    b"\x00" * TAG_SIZE + rlp.encode((
        [b"\x00"] * NONCE_SIZE,
        b"\x00" * ID_NONCE_SIZE,
        b"gcm",
        b"",
        b"",
    )),
    # auth header with id nonce being a list
    b"\x00" * TAG_SIZE + rlp.encode((
        b"\x00" * NONCE_SIZE,
        [b"\x00"] * ID_NONCE_SIZE,
        b"gcm",
        b"",
        b"",
    )),
    # auth header with public key being a list
    b"\x00" * TAG_SIZE + rlp.encode((
        b"\x00" * NONCE_SIZE,
        b"\x00" * ID_NONCE_SIZE,
        b"gcm",
        [b""],
        b"",
    )),
    # auth header with auth response being a list
    b"\x00" * TAG_SIZE + rlp.encode((
        b"\x00" * NONCE_SIZE,
        b"\x00" * ID_NONCE_SIZE,
        b"gcm",
        b"",
        [b""],
    )),
    # auth header with oversized message
    b"\x00" * TAG_SIZE + rlp.encode((
        b"\x00" * NONCE_SIZE,
        b"\x00" * ID_NONCE_SIZE,
        b"gcm",
        b"",
        b"",
    )) + b"\x00" * 2000,

    # auth tag with invalid size
    b"\x00" * TAG_SIZE + rlp.encode(b"\x00" * (NONCE_SIZE - 1)),
    # auth tag with oversized message
    b"\x00" * TAG_SIZE + rlp.encode(b"\x00" * NONCE_SIZE) + b"\x00" * 2000,
))
def test_invalid_message_packet_decoding(encoded_packet):
    with pytest.raises(ValidationError):
        decode_message_packet(encoded_packet)


@given(
    magic=magic_st,
    token=nonce_st,
    id_nonce=id_nonce_st,
    enr_seq=enr_seq_st,
)
def test_who_are_you_encoding_decoding(magic, token, id_nonce, enr_seq):
    original_packet = WhoAreYouPacket(
        magic=magic,
        token=token,
        id_nonce=id_nonce,
        enr_sequence_number=enr_seq,
    )
    encoded_packet = original_packet.to_wire_bytes()
    decoded_packet = decode_who_are_you_packet(encoded_packet)
    assert decoded_packet == original_packet


@pytest.mark.parametrize("encoded_packet", (
    b"",  # empty
    b"\x00" * MAGIC_SIZE,  # no payload
    b"\x00" * 500,  # invalid RLP payload
    b"\x00" * MAGIC_SIZE + rlp.encode(b"payload"),  # payload is not a list
    # payload too short
    b"\x00" * MAGIC_SIZE + rlp.encode((b"\x00" * NONCE_SIZE, b"")),
    # payload too long
    b"\x00" * MAGIC_SIZE + rlp.encode((b"\x00" * NONCE_SIZE, b"", b"", b"")),
    b"\x00" * (MAGIC_SIZE - 1) + rlp.encode((b"\x00" * NONCE_SIZE, b"", 0)),  # too short
    b"\x00" * MAGIC_SIZE + rlp.encode((b"\x00" * 11, b"", 0)),  # invalid nonce
    # too long
    b"\x00" * MAGIC_SIZE + rlp.encode((b"\x00" * NONCE_SIZE, b"\x00" * 2000, 0)),
))
def test_invalid_who_are_you_decoding(encoded_packet):
    with pytest.raises(ValidationError):
        decode_who_are_you_packet(encoded_packet)


def test_invalid_who_are_you_encoding():
    packet = WhoAreYouPacket(
        magic=b"\x00" * MAGIC_SIZE,
        token=b"\x00" * NONCE_SIZE,
        id_nonce=b"\x00" * 2000,
        enr_sequence_number=0,
    )
    with pytest.raises(ValidationError):
        packet.to_wire_bytes()


@pytest.mark.parametrize("packet", (
    WhoAreYouPacketFactory(),
    AuthTagPacketFactory(),
    AuthHeaderPacketFactory(),
))
def test_packet_decoding(packet):
    encoded_packet = packet.to_wire_bytes()
    decoded_packet = decode_packet(encoded_packet)
    assert decoded_packet == packet
