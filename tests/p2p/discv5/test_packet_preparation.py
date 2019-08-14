from hypothesis import (
    given,
)

import rlp

from eth_utils import (
    int_to_big_endian,
    is_list_like,
)

from p2p.discv5.packets import (
    AuthHeaderPacket,
    AuthTagPacket,
    WhoAreYouPacket,
)
from p2p.discv5.enr import (
    ENR,
)
from p2p.discv5.messages import (
    PingMessage,
)
from p2p.discv5.encryption import (
    aesgcm_decrypt,
)
from p2p.discv5.constants import (
    AUTH_RESPONSE_VERSION,
    AUTH_SCHEME_NAME,
    MAGIC_SIZE,
    ZERO_NONCE,
)

from tests.p2p.discv5.strategies import (
    key_st,
    nonce_st,
    public_key_st,
    tag_st,
    node_id_st,
    id_nonce_st,
    enr_seq_st,
    random_data_st,
)


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    id_nonce=id_nonce_st,
    initiator_key=key_st,
    auth_response_key=key_st,
    ephemeral_public_key=public_key_st,
)
def test_auth_header_preparation(tag,
                                 auth_tag,
                                 id_nonce,
                                 initiator_key,
                                 auth_response_key,
                                 ephemeral_public_key):
    enr = ENR(
        sequence_number=1,
        signature=b"",
        kv_pairs={
            b"id": b"v4",
            b"secp256k1": b"\x02" * 33,
        }
    )
    message = PingMessage(
        request_id=5,
        enr_seq=enr.sequence_number,
    )
    id_nonce_signature = b"\x00" * 32

    packet = AuthHeaderPacket.prepare(
        tag=tag,
        auth_tag=auth_tag,
        id_nonce=id_nonce,
        message=message,
        initiator_key=initiator_key,
        id_nonce_signature=id_nonce_signature,
        auth_response_key=auth_response_key,
        enr=enr,
        ephemeral_public_key=ephemeral_public_key
    )

    assert packet.tag == tag
    assert packet.auth_header.auth_tag == auth_tag
    assert packet.auth_header.id_nonce == id_nonce
    assert packet.auth_header.auth_scheme_name == AUTH_SCHEME_NAME
    assert packet.auth_header.ephemeral_public_key == ephemeral_public_key

    decrypted_auth_response = aesgcm_decrypt(
        key=auth_response_key,
        nonce=ZERO_NONCE,
        cipher_text=packet.auth_header.encrypted_auth_response,
        authenticated_data=b"",
    )
    decoded_auth_response = rlp.decode(decrypted_auth_response)
    assert is_list_like(decoded_auth_response) and len(decoded_auth_response) == 3
    assert decoded_auth_response[0] == int_to_big_endian(AUTH_RESPONSE_VERSION)
    assert decoded_auth_response[1] == id_nonce_signature
    assert ENR.deserialize(decoded_auth_response[2]) == enr

    decrypted_message = aesgcm_decrypt(
        key=initiator_key,
        nonce=auth_tag,
        cipher_text=packet.encrypted_message,
        authenticated_data=b"".join((
            tag,
            rlp.encode(packet.auth_header),
        ))
    )
    assert decrypted_message[0] == message.message_type
    assert rlp.decode(decrypted_message[1:], PingMessage) == message


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    random_data=random_data_st,
)
def test_random_packet_preparation(tag, auth_tag, random_data):
    packet = AuthTagPacket.prepare_random(
        tag=tag,
        auth_tag=auth_tag,
        random_data=random_data,
    )
    assert packet.tag == tag
    assert packet.auth_tag == auth_tag
    assert packet.encrypted_message == random_data


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    id_nonce=id_nonce_st,
    initiator_key=key_st,
    auth_response_key=key_st,
    ephemeral_public_key=public_key_st,
)
def test_auth_header_preparation_without_enr(tag,
                                             auth_tag,
                                             id_nonce,
                                             initiator_key,
                                             auth_response_key,
                                             ephemeral_public_key):
    message = PingMessage(
        request_id=5,
        enr_seq=1,
    )
    id_nonce_signature = b"\x00" * 32

    packet = AuthHeaderPacket.prepare(
        tag=tag,
        auth_tag=auth_tag,
        id_nonce=id_nonce,
        message=message,
        initiator_key=initiator_key,
        id_nonce_signature=id_nonce_signature,
        auth_response_key=auth_response_key,
        enr=None,
        ephemeral_public_key=ephemeral_public_key
    )

    decrypted_auth_response = aesgcm_decrypt(
        key=auth_response_key,
        nonce=ZERO_NONCE,
        cipher_text=packet.auth_header.encrypted_auth_response,
        authenticated_data=b"",
    )
    decoded_auth_response = rlp.decode(decrypted_auth_response)
    assert is_list_like(decoded_auth_response) and len(decoded_auth_response) == 3
    assert decoded_auth_response[0] == int_to_big_endian(AUTH_RESPONSE_VERSION)
    assert decoded_auth_response[1] == id_nonce_signature
    assert decoded_auth_response[2] == []


@given(
    node_id=node_id_st,
    token=nonce_st,
    id_nonce=id_nonce_st,
    enr_seq=enr_seq_st,
)
def test_who_are_you_preparation(node_id, token, id_nonce, enr_seq):
    packet = WhoAreYouPacket.prepare(
        destination_node_id=node_id,
        token=token,
        id_nonce=id_nonce,
        enr_sequence_number=enr_seq,
    )
    assert packet.token == token
    assert packet.id_nonce == id_nonce
    assert packet.enr_sequence_number == enr_seq
    assert len(packet.magic) == MAGIC_SIZE


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    key=key_st,
)
def test_auth_tag_packet_preparation(tag, auth_tag, key):
    message = PingMessage(
        request_id=5,
        enr_seq=3,
    )

    packet = AuthTagPacket.prepare(
        tag=tag,
        auth_tag=auth_tag,
        message=message,
        key=key,
    )
    assert packet.tag == tag
    assert packet.auth_tag == auth_tag
    decrypted_message = aesgcm_decrypt(
        key=key,
        nonce=auth_tag,
        cipher_text=packet.encrypted_message,
        authenticated_data=tag,
    )
    assert decrypted_message[0] == message.message_type
    assert rlp.decode(decrypted_message[1:], PingMessage) == message
