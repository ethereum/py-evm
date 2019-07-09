from hypothesis import (
    given,
)

import rlp

from eth_utils import (
    is_list_like,
)

from p2p.discv5.packets import (
    prepare_auth_header_packet,
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
    AUTH_SCHEME_NAME,
    ZERO_NONCE,
)

from tests.p2p.discv5.strategies import (
    key_st,
    nonce_st,
    pubkey_st,
    tag_st,
)


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    initiator_key=key_st,
    auth_response_key=key_st,
    ephemeral_pubkey=pubkey_st,
)
def test_auth_header_preparation(tag,
                                 auth_tag,
                                 initiator_key,
                                 auth_response_key,
                                 ephemeral_pubkey):
    enr = ENR(
        sequence_number=1,
        signature=b"",
        kv_pairs={
            b"id": b"v4",
        }
    )
    message = PingMessage(
        request_id=5,
        enr_seq=enr.sequence_number,
    )
    id_nonce_signature = b"\x00" * 32

    packet = prepare_auth_header_packet(
        tag=tag,
        auth_tag=auth_tag,
        message=message,
        initiator_key=initiator_key,
        id_nonce_signature=id_nonce_signature,
        auth_response_key=auth_response_key,
        enr=enr,
        ephemeral_pubkey=ephemeral_pubkey
    )

    assert packet.tag == tag
    assert packet.auth_header.auth_tag == auth_tag
    assert packet.auth_header.auth_scheme_name == AUTH_SCHEME_NAME
    assert packet.auth_header.ephemeral_pubkey == ephemeral_pubkey

    decrypted_auth_response = aesgcm_decrypt(
        key=auth_response_key,
        nonce=ZERO_NONCE,
        cipher_text=packet.auth_header.encrypted_auth_response,
        authenticated_data=tag,
    )
    decoded_auth_response = rlp.decode(decrypted_auth_response)
    assert is_list_like(decoded_auth_response) and len(decoded_auth_response) == 2
    assert decoded_auth_response[0] == id_nonce_signature
    assert ENR.deserialize(decoded_auth_response[1]) == enr

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
    initiator_key=key_st,
    auth_response_key=key_st,
    ephemeral_pubkey=pubkey_st,
)
def test_auth_header_preparation_without_enr(tag,
                                             auth_tag,
                                             initiator_key,
                                             auth_response_key,
                                             ephemeral_pubkey):
    message = PingMessage(
        request_id=5,
        enr_seq=1,
    )
    id_nonce_signature = b"\x00" * 32

    packet = prepare_auth_header_packet(
        tag=tag,
        auth_tag=auth_tag,
        message=message,
        initiator_key=initiator_key,
        id_nonce_signature=id_nonce_signature,
        auth_response_key=auth_response_key,
        enr=None,
        ephemeral_pubkey=ephemeral_pubkey
    )

    decrypted_auth_response = aesgcm_decrypt(
        key=auth_response_key,
        nonce=ZERO_NONCE,
        cipher_text=packet.auth_header.encrypted_auth_response,
        authenticated_data=tag,
    )
    decoded_auth_response = rlp.decode(decrypted_auth_response)
    assert is_list_like(decoded_auth_response) and len(decoded_auth_response) == 2
    assert decoded_auth_response[0] == id_nonce_signature
    assert decoded_auth_response[1] == []
