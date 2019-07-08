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
    AuthHeader,
    decode_message_packet,
)
from p2p.discv5.constants import (
    NONCE_SIZE,
    TAG_SIZE,
    MAX_PACKET_SIZE,
    AUTH_SCHEME_NAME,
)


nonce_st = st.binary(min_size=NONCE_SIZE, max_size=NONCE_SIZE)
tag_st = st.binary(min_size=TAG_SIZE, max_size=TAG_SIZE)
# arbitrary as we're not working with a particular identity scheme
pubkey_st = st.binary(min_size=33, max_size=33)


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
    original_packet = AuthTagPacket(
        tag=tag,
        auth_tag=auth_tag,
        encrypted_message=encrypted_message,
    )
    encoded_packet = original_packet.to_wire_bytes()
    decoded_packet = decode_message_packet(encoded_packet)
    assert isinstance(decoded_packet, AuthTagPacket)
    assert decoded_packet == original_packet


def test_oversize_auth_tag_packet_encoding():
    packet = AuthTagPacket(
        tag=b"\x00" * TAG_SIZE,
        auth_tag=b"\x00" * NONCE_SIZE,
        encrypted_message=b"\x00" * (MAX_PACKET_SIZE - (1 + TAG_SIZE) - NONCE_SIZE + 1),
    )
    with pytest.raises(ValidationError):
        packet.to_wire_bytes()


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    ephemeral_pubkey=pubkey_st,
    encrypted_auth_response=st.binary(min_size=16, max_size=32),
    encrypted_message_size=st.integers(
        min_value=0,
        # account for various RLP prefixes in auth header and assume max length for all entries
        max_value=MAX_PACKET_SIZE - TAG_SIZE - sum((
            2,  # rlp list prefix
            1 + NONCE_SIZE,  # tag
            1 + len(AUTH_SCHEME_NAME),  # auth scheme name
            1 + 33,  # pubkey
            1 + 32,  # encrypted auth response
        ))
    ),
)
def test_auth_header_packet_encoding_decoding(tag,
                                              auth_tag,
                                              ephemeral_pubkey,
                                              encrypted_auth_response,
                                              encrypted_message_size):
    auth_header = AuthHeader(
        auth_tag=auth_tag,
        auth_scheme_name=AUTH_SCHEME_NAME,
        ephemeral_pubkey=ephemeral_pubkey,
        encrypted_auth_response=encrypted_auth_response,
    )
    encrypted_message = b"\x00" * encrypted_message_size
    original_packet = AuthHeaderPacket(
        tag=tag,
        auth_header=auth_header,
        encrypted_message=encrypted_message,
    )
    encoded_packet = original_packet.to_wire_bytes()
    decoded_packet = decode_message_packet(encoded_packet)
    assert isinstance(decoded_packet, AuthHeaderPacket)
    assert decoded_packet == original_packet


def test_oversize_auth_header_packet_encoding():
    auth_header = AuthHeader(
        auth_tag=b"\x00" * NONCE_SIZE,
        auth_scheme_name=AUTH_SCHEME_NAME,
        ephemeral_pubkey=b"\x00" * 32,
        encrypted_auth_response=32,
    )
    header_size = len(rlp.encode(auth_header))
    encrypted_message_size = MAX_PACKET_SIZE - TAG_SIZE - header_size + 1
    encrypted_message = b"\x00" * encrypted_message_size
    packet = AuthHeaderPacket(
        tag=b"\x00" * TAG_SIZE,
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
    b"\x00" * TAG_SIZE + rlp.encode((b"\x00" * NONCE_SIZE, AUTH_SCHEME_NAME, b"")),
    # auth header with too many elements
    b"\x00" * TAG_SIZE + rlp.encode((b"\x00" * NONCE_SIZE, AUTH_SCHEME_NAME, b"", b"", b"")),
    # auth header with invalid tag
    b"\x00" * TAG_SIZE + rlp.encode((b"\x00" * (NONCE_SIZE - 1), AUTH_SCHEME_NAME, b"", b"")),
    # auth header with wrong auth scheme
    b"\x00" * TAG_SIZE + rlp.encode((b"\x00" * NONCE_SIZE, b"no-gcm", b"", b"")),
    # auth header with tag being a list
    b"\x00" * TAG_SIZE + rlp.encode(([b"\x00"] * NONCE_SIZE, b"gcm", b"", b"")),
    # auth header with public key being a list
    b"\x00" * TAG_SIZE + rlp.encode((b"\x00" * NONCE_SIZE, b"gcm", [b""], b"")),
    # auth header with auth response being a list
    b"\x00" * TAG_SIZE + rlp.encode((b"\x00" * NONCE_SIZE, b"gcm", b"", [b""])),
    # auth header with oversized message
    b"\x00" * TAG_SIZE + rlp.encode((b"\x00" * NONCE_SIZE, b"gcm", b"", b"")) + b"\x00" * 2000,
    # auth tag with invalid size
    b"\x00" * TAG_SIZE + rlp.encode(b"\x00" * (NONCE_SIZE - 1)),
    # auth tag with oversized message
    b"\x00" * TAG_SIZE + rlp.encode(b"\x00" * NONCE_SIZE) + b"\x00" * 2000,
))
def test_invalid_message_packet_decoding(encoded_packet):
    with pytest.raises(ValidationError):
        decode_message_packet(encoded_packet)
