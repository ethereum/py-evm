from eth_utils import (
    keccak,
)

from p2p.tools.factories.discovery import (
    AuthTagPacketFactory,
    ENRFactory,
    HandshakeInitiatorFactory,
    HandshakeRecipientFactory,
    PingMessageFactory,
    WhoAreYouPacketFactory,
)
from p2p.tools.factories.keys import (
    PrivateKeyFactory,
)


def assert_session_keys_equal(initiator_session_keys, recipient_session_keys):
    assert initiator_session_keys.auth_response_key == recipient_session_keys.auth_response_key
    assert initiator_session_keys.encryption_key == recipient_session_keys.decryption_key
    assert initiator_session_keys.decryption_key == recipient_session_keys.encryption_key


def test_initiator_expects_who_are_you_response():
    handshake_initiator = HandshakeInitiatorFactory()
    expected_token = handshake_initiator.first_packet_to_send.auth_tag
    unexpected_token = keccak(expected_token)

    assert not handshake_initiator.is_response_packet(AuthTagPacketFactory())
    assert not handshake_initiator.is_response_packet(WhoAreYouPacketFactory(
        token=unexpected_token,
    ))
    assert handshake_initiator.is_response_packet(WhoAreYouPacketFactory(
        token=expected_token,
    ))


def test_successful_handshake():
    initiator_private_key = PrivateKeyFactory().to_bytes()
    recipient_private_key = PrivateKeyFactory().to_bytes()
    initiator_enr = ENRFactory(private_key=initiator_private_key)
    recipient_enr = ENRFactory(private_key=recipient_private_key)
    initial_message = PingMessageFactory()

    initiator = HandshakeInitiatorFactory(
        local_private_key=initiator_private_key,
        local_enr=initiator_enr,
        remote_enr=recipient_enr,
        initial_message=initial_message,
    )
    recipient = HandshakeRecipientFactory(
        local_private_key=recipient_private_key,
        local_enr=recipient_enr,
        remote_enr=initiator_enr,
        initiating_packet_auth_tag=initiator.first_packet_to_send.auth_tag
    )

    initiator_result = initiator.complete_handshake(recipient.first_packet_to_send)
    recipient_result = recipient.complete_handshake(initiator_result.auth_header_packet)

    assert_session_keys_equal(initiator_result.session_keys, recipient_result.session_keys)

    assert initiator_result.message is None
    assert initiator_result.enr is None
    assert initiator_result.auth_header_packet is not None

    assert recipient_result.message == initial_message
    assert recipient_result.enr is None
    assert recipient_result.auth_header_packet is None


def test_successful_handshake_with_enr_update():
    initiator_private_key = PrivateKeyFactory().to_bytes()
    recipient_private_key = PrivateKeyFactory().to_bytes()
    old_initiator_enr = ENRFactory(private_key=initiator_private_key)
    new_initiator_enr = ENRFactory(
        private_key=initiator_private_key,
        sequence_number=old_initiator_enr.sequence_number + 1,
    )

    initiator = HandshakeInitiatorFactory(
        local_private_key=initiator_private_key,
        local_enr=new_initiator_enr,
        remote_private_key=recipient_private_key,
    )
    recipient = HandshakeRecipientFactory(
        local_private_key=recipient_private_key,
        remote_enr=old_initiator_enr,
        initiating_packet_auth_tag=initiator.first_packet_to_send.auth_tag
    )

    initiator_result = initiator.complete_handshake(recipient.first_packet_to_send)
    recipient_result = recipient.complete_handshake(initiator_result.auth_header_packet)

    assert initiator_result.enr is None
    assert recipient_result.enr == new_initiator_enr


def test_successful_handshake_with_new_enr():
    initiator_private_key = PrivateKeyFactory().to_bytes()
    recipient_private_key = PrivateKeyFactory().to_bytes()
    initiator_enr = ENRFactory(private_key=initiator_private_key)
    recipient_enr = ENRFactory(private_key=recipient_private_key)

    initiator = HandshakeInitiatorFactory(
        local_private_key=initiator_private_key,
        local_enr=initiator_enr,
        remote_enr=recipient_enr,
    )
    recipient = HandshakeRecipientFactory(
        local_private_key=recipient_private_key,
        local_enr=recipient_enr,
        remote_enr=None,
        remote_node_id=initiator_enr.node_id,
        initiating_packet_auth_tag=initiator.first_packet_to_send.auth_tag
    )

    initiator_result = initiator.complete_handshake(recipient.first_packet_to_send)
    recipient_result = recipient.complete_handshake(initiator_result.auth_header_packet)

    assert initiator_result.enr is None
    assert recipient_result.enr == initiator_enr
