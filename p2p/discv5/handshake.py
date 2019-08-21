from typing import (
    Optional,
    Type,
)
import secrets

from eth_utils import (
    encode_hex,
    ValidationError,
)

from p2p.exceptions import (
    DecryptionError,
    HandshakeFailure,
)

from p2p.discv5.abc import HandshakeParticipantAPI
from p2p.discv5.enr import ENR
from p2p.discv5.identity_schemes import IdentityScheme
from p2p.discv5.messages import BaseMessage
from p2p.discv5.packets import (
    AuthHeaderPacket,
    AuthTagPacket,
    get_random_auth_tag,
    get_random_encrypted_data,
    get_random_id_nonce,
    Packet,
    WhoAreYouPacket,
)
from p2p.discv5.tags import (
    compute_tag,
    recover_source_id_from_tag,
)
from p2p.discv5.typing import (
    AES128Key,
    IDNonce,
    NodeID,
    Nonce,
    HandshakeResult,
    Tag,
)


class BaseHandshakeParticipant(HandshakeParticipantAPI):
    def __init__(self,
                 is_initiator: bool,
                 local_private_key: bytes,
                 local_enr: ENR,
                 remote_node_id: NodeID,
                 ) -> None:
        self._is_initiator = is_initiator

        self._local_enr = local_enr
        self._local_private_key = local_private_key
        self._remote_node_id = remote_node_id

    @property
    def is_initiator(self) -> bool:
        return self._is_initiator

    @property
    def local_private_key(self) -> bytes:
        return self._local_private_key

    @property
    def local_enr(self) -> ENR:
        return self._local_enr

    @property
    def local_node_id(self) -> NodeID:
        return self.local_enr.node_id

    @property
    def remote_node_id(self) -> NodeID:
        return self._remote_node_id

    @property
    def tag(self) -> Tag:
        return compute_tag(
            source_node_id=self.local_node_id,
            destination_node_id=self.remote_node_id,
        )


class HandshakeInitiator(BaseHandshakeParticipant):
    def __init__(self,
                 *,
                 local_private_key: bytes,
                 local_enr: ENR,
                 remote_enr: ENR,
                 initial_message: BaseMessage,
                 ) -> None:
        super().__init__(
            is_initiator=True,
            local_enr=local_enr,
            local_private_key=local_private_key,
            remote_node_id=remote_enr.node_id,
        )
        self.remote_enr = remote_enr
        self.initial_message = initial_message

        self.initiating_packet = AuthTagPacket.prepare_random(
            tag=self.tag,
            auth_tag=get_random_auth_tag(),
            random_data=get_random_encrypted_data(),
        )

    @property
    def identity_scheme(self) -> Type[IdentityScheme]:
        return self.remote_enr.identity_scheme

    @property
    def first_packet_to_send(self) -> Packet:
        return self.initiating_packet

    def is_response_packet(self, packet: Packet) -> bool:
        return (
            isinstance(packet, WhoAreYouPacket) and
            secrets.compare_digest(packet.token, self.initiating_packet.auth_tag)
        )

    def complete_handshake(self, response_packet: Packet) -> HandshakeResult:
        if not self.is_response_packet(response_packet):
            raise ValueError(f"Packet {response_packet} is not the expected response packet")
        if not isinstance(response_packet, WhoAreYouPacket):
            raise TypeError("Invariant: Only WhoAreYou packets are valid responses")
        who_are_you_packet = response_packet

        # compute session keys
        (
            ephemeral_private_key,
            ephemeral_public_key,
        ) = self.identity_scheme.create_handshake_key_pair()

        session_keys = self.identity_scheme.compute_session_keys(
            local_private_key=ephemeral_private_key,
            remote_public_key=self.remote_enr.public_key,
            local_node_id=self.local_enr.node_id,
            remote_node_id=self.remote_node_id,
            id_nonce=who_are_you_packet.id_nonce,
            is_locally_initiated=True,
        )

        # prepare response packet
        id_nonce_signature = self.identity_scheme.create_id_nonce_signature(
            id_nonce=who_are_you_packet.id_nonce,
            private_key=self.local_private_key,
        )

        if who_are_you_packet.enr_sequence_number < self.local_enr.sequence_number:
            enr = self.local_enr
        else:
            enr = None

        auth_header_packet = AuthHeaderPacket.prepare(
            tag=self.tag,
            auth_tag=get_random_auth_tag(),
            id_nonce=who_are_you_packet.id_nonce,
            message=self.initial_message,
            initiator_key=session_keys.encryption_key,
            id_nonce_signature=id_nonce_signature,
            auth_response_key=session_keys.auth_response_key,
            enr=enr,
            ephemeral_public_key=ephemeral_public_key,
        )

        return HandshakeResult(
            session_keys=session_keys,
            enr=None,
            message=None,
            auth_header_packet=auth_header_packet,
        )


class HandshakeRecipient(BaseHandshakeParticipant):
    def __init__(self,
                 *,
                 local_private_key: bytes,
                 local_enr: ENR,
                 remote_node_id: Optional[NodeID],
                 remote_enr: Optional[ENR],
                 initiating_packet_auth_tag: Nonce,
                 ) -> None:
        if remote_enr is None and remote_node_id is None:
            raise ValueError("Either the peer's ENR, its node id, or both must be given")
        elif remote_enr is not None and remote_node_id is not None:
            if remote_node_id != remote_enr.node_id:
                raise ValueError(
                    f"Node id according to ENR ({encode_hex(remote_enr.node_id)}) must match "
                    f"explicitly given one ({encode_hex(remote_node_id)})"
                )
        if remote_node_id is None:
            remote_node_id = remote_enr.node_id

        super().__init__(
            is_initiator=False,
            local_enr=local_enr,
            local_private_key=local_private_key,
            remote_node_id=remote_node_id,
        )
        self.remote_enr = remote_enr

        if self.remote_enr is not None:
            enr_sequence_number = self.remote_enr.sequence_number
        else:
            enr_sequence_number = 0
        self.who_are_you_packet = WhoAreYouPacket.prepare(
            destination_node_id=self.remote_node_id,
            token=initiating_packet_auth_tag,
            id_nonce=get_random_id_nonce(),
            enr_sequence_number=enr_sequence_number,
        )

    @property
    def identity_scheme(self) -> Type[IdentityScheme]:
        return self.local_enr.identity_scheme

    @property
    def first_packet_to_send(self) -> Packet:
        return self.who_are_you_packet

    def is_response_packet(self, packet: Packet) -> bool:
        return (
            isinstance(packet, AuthHeaderPacket) and
            recover_source_id_from_tag(
                packet.tag,
                self.local_node_id,
            ) == self.remote_node_id
        )

    def complete_handshake(self, response_packet: Packet) -> HandshakeResult:
        if not self.is_response_packet(response_packet):
            raise ValueError("Packet is not the expected response packet")
        if not isinstance(response_packet, AuthHeaderPacket):
            raise TypeError("Invariant: Only AuthHeader packets are valid responses")
        auth_header_packet = response_packet

        ephemeral_public_key = auth_header_packet.auth_header.ephemeral_public_key
        try:
            self.identity_scheme.validate_handshake_public_key(ephemeral_public_key)
        except ValidationError as error:
            raise HandshakeFailure(
                f"AuthHeader packet from contains invalid ephemeral public key "
                f"{encode_hex(ephemeral_public_key)}"
            ) from error

        session_keys = self.identity_scheme.compute_session_keys(
            local_private_key=self.local_private_key,
            remote_public_key=ephemeral_public_key,
            local_node_id=self.local_enr.node_id,
            remote_node_id=self.remote_node_id,
            id_nonce=self.who_are_you_packet.id_nonce,
            is_locally_initiated=False,
        )

        enr = self.decrypt_and_validate_auth_response(
            auth_header_packet,
            session_keys.auth_response_key,
            self.who_are_you_packet.id_nonce,
        )
        message = self.decrypt_and_validate_message(
            auth_header_packet,
            session_keys.decryption_key,
        )

        return HandshakeResult(
            session_keys=session_keys,
            enr=enr,
            message=message,
            auth_header_packet=None,
        )

    def decrypt_and_validate_auth_response(self,
                                           auth_header_packet: AuthHeaderPacket,
                                           auth_response_key: AES128Key,
                                           id_nonce: IDNonce,
                                           ) -> Optional[ENR]:
        try:
            id_nonce_signature, enr = auth_header_packet.decrypt_auth_response(auth_response_key)
        except DecryptionError as error:
            raise HandshakeFailure("Unable to decrypt auth response") from error
        except ValidationError as error:
            raise HandshakeFailure("Invalid auth response content") from error

        # validate ENR if present
        if enr is None:
            if self.remote_enr is None:
                raise HandshakeFailure("Peer failed to send their ENR")
            else:
                current_remote_enr = self.remote_enr
        else:
            try:
                enr.validate_signature()
            except ValidationError as error:
                raise HandshakeFailure("ENR in auth response contains invalid signature") from error

            if self.remote_enr is not None:
                if enr.sequence_number <= self.remote_enr.sequence_number:
                    raise HandshakeFailure(
                        "ENR in auth response is not newer than what we already have"
                    )

            if enr.node_id != self.remote_node_id:
                raise HandshakeFailure(
                    f"ENR received from peer belongs to different node ({encode_hex(enr.node_id)} "
                    f"instead of {encode_hex(self.remote_node_id)})"
                )

            current_remote_enr = enr

        try:
            self.identity_scheme.validate_id_nonce_signature(
                signature=id_nonce_signature,
                id_nonce=id_nonce,
                public_key=current_remote_enr.public_key,
            )
        except ValidationError as error:
            raise HandshakeFailure("Invalid id nonce signature in auth response") from error

        return enr

    def decrypt_and_validate_message(self,
                                     auth_header_packet: AuthHeaderPacket,
                                     decryption_key: AES128Key
                                     ) -> BaseMessage:
        try:
            return auth_header_packet.decrypt_message(decryption_key)
        except DecryptionError as error:
            raise HandshakeFailure(
                "Failed to decrypt message in AuthHeader packet with newly established session keys"
            ) from error
        except ValidationError as error:
            raise HandshakeFailure("Received invalid message") from error
