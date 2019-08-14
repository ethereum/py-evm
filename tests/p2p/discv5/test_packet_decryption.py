import pytest

from hypothesis import (
    given,
)

from eth_keys.datatypes import (
    PrivateKey,
)

from p2p.exceptions import (
    DecryptionError,
)

from p2p.discv5.packets import (
    AuthHeaderPacket,
    AuthTagPacket,
)
from p2p.discv5.enr import (
    ENR,
)
from p2p.discv5.messages import (
    PingMessage,
)
from p2p.discv5.constants import (
    AES128_KEY_SIZE,
)

from tests.p2p.discv5.strategies import (
    id_nonce_st,
    tag_st,
    nonce_st,
    key_st,
    public_key_st,
)


@pytest.fixture
def enr():
    return ENR(
        sequence_number=1,
        signature=b"",
        kv_pairs={
            b"id": b"v4",
            b"secp256k1": PrivateKey(b"\x01" * 32).public_key.to_compressed_bytes(),
        }
    )


@pytest.fixture
def message(enr):
    return PingMessage(
        request_id=5,
        enr_seq=enr.sequence_number,
    )


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    id_nonce=id_nonce_st,
    initiator_key=key_st,
    auth_response_key=key_st,
    ephemeral_public_key=public_key_st,
)
def test_auth_header_message_decryption(tag,
                                        auth_tag,
                                        id_nonce,
                                        initiator_key,
                                        auth_response_key,
                                        ephemeral_public_key,
                                        enr,
                                        message):
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

    decrypted_message = packet.decrypt_message(initiator_key)
    assert decrypted_message == message


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    id_nonce=id_nonce_st,
    initiator_key=key_st,
    auth_response_key=key_st,
    ephemeral_public_key=public_key_st,
)
def test_auth_header_decryption_with_enr(tag,
                                         auth_tag,
                                         id_nonce,
                                         initiator_key,
                                         auth_response_key,
                                         ephemeral_public_key,
                                         enr,
                                         message):
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

    recovered_id_nonce_signature, recovered_enr = packet.decrypt_auth_response(auth_response_key)
    assert recovered_id_nonce_signature == id_nonce_signature
    assert recovered_enr == enr


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    id_nonce=id_nonce_st,
    initiator_key=key_st,
    auth_response_key=key_st,
    ephemeral_public_key=public_key_st,
)
def test_auth_header_decryption_without_enr(tag,
                                            auth_tag,
                                            id_nonce,
                                            initiator_key,
                                            auth_response_key,
                                            ephemeral_public_key,
                                            message):
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

    recovered_id_nonce_signature, recovered_enr = packet.decrypt_auth_response(auth_response_key)
    assert recovered_id_nonce_signature == id_nonce_signature
    assert recovered_enr is None


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    id_nonce=id_nonce_st,
    initiator_key=key_st,
    ephemeral_public_key=public_key_st,
)
def test_invalid_auth_header_decryption_with_wrong_key(tag,
                                                       auth_tag,
                                                       id_nonce,
                                                       initiator_key,
                                                       ephemeral_public_key,
                                                       message):
    id_nonce_signature = b"\x00" * 32
    encryption_key = b"\x00" * AES128_KEY_SIZE
    decryption_key = b"\x11" * AES128_KEY_SIZE
    packet = AuthHeaderPacket.prepare(
        tag=tag,
        auth_tag=auth_tag,
        id_nonce=id_nonce,
        message=message,
        initiator_key=initiator_key,
        id_nonce_signature=id_nonce_signature,
        auth_response_key=encryption_key,
        enr=None,
        ephemeral_public_key=ephemeral_public_key
    )
    with pytest.raises(DecryptionError):
        packet.decrypt_auth_response(decryption_key)


@given(
    tag=tag_st,
    auth_tag=nonce_st,
    key=key_st,
)
def test_auth_tag_message_decryption(tag, auth_tag, key, message):
    packet = AuthTagPacket.prepare(
        tag=tag,
        auth_tag=auth_tag,
        message=message,
        key=key,
    )

    decrypted_message = packet.decrypt_message(key)
    assert decrypted_message == message
