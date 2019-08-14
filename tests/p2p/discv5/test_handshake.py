from eth_utils import (
    keccak,
)

from p2p.tools.factories import (
    AuthTagPacketFactory,
    ENRFactory,
    HandshakeInitiatorFactory,
    HandshakeRecipientFactory,
    PingMessageFactory,
    PrivateKeyFactory,
    WhoAreYouPacketFactory,
)


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
        our_private_key=initiator_private_key,
        our_enr=initiator_enr,
        their_enr=recipient_enr,
        initial_message=initial_message,
    )
    recipient = HandshakeRecipientFactory(
        our_private_key=recipient_private_key,
        our_enr=recipient_enr,
        their_enr=initiator_enr,
        initiating_packet_auth_tag=initiator.first_packet_to_send.auth_tag
    )

    initiator_result = initiator.complete_handshake(recipient.first_packet_to_send)
    recipient_result = recipient.complete_handshake(initiator_result.auth_header_packet)

    assert initiator_result.session_keys == recipient_result.session_keys

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
        our_private_key=initiator_private_key,
        our_enr=new_initiator_enr,
        their_private_key=recipient_private_key,
    )
    recipient = HandshakeRecipientFactory(
        our_private_key=recipient_private_key,
        their_enr=old_initiator_enr,
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
        our_private_key=initiator_private_key,
        our_enr=initiator_enr,
        their_enr=recipient_enr,
    )
    recipient = HandshakeRecipientFactory(
        our_private_key=recipient_private_key,
        our_enr=recipient_enr,
        their_enr=None,
        their_node_id=initiator_enr.node_id,
        initiating_packet_auth_tag=initiator.first_packet_to_send.auth_tag
    )

    initiator_result = initiator.complete_handshake(recipient.first_packet_to_send)
    recipient_result = recipient.complete_handshake(initiator_result.auth_header_packet)

    assert initiator_result.enr is None
    assert recipient_result.enr == initiator_enr
