import socket
from typing import (
    Any,
    Dict,
)

import factory

from eth_keys import keys

from eth_utils import keccak
from eth_utils.toolz import merge

from p2p.discovery import DiscoveryProtocol
from p2p.discv5.packets import (
    AuthHeader,
    AuthHeaderPacket,
    AuthTagPacket,
    WhoAreYouPacket,
)
from p2p.discv5.constants import (
    AUTH_SCHEME_NAME,
    ID_NONCE_SIZE,
    NONCE_SIZE,
    MAGIC_SIZE,
    TAG_SIZE,
)
from p2p.discv5.channel_services import (
    Endpoint,
    IncomingPacket,
)
from p2p.discv5.endpoint_tracker import (
    EndpointVote,
)
from p2p.discv5.enr import (
    ENR,
    UnsignedENR,
)
from p2p.discv5.identity_schemes import (
    V4IdentityScheme,
)
from p2p.discv5.messages import (
    PingMessage,
)
from p2p.discv5.handshake import (
    HandshakeInitiator,
    HandshakeRecipient,
)
from p2p.discv5.typing import (
    NodeID,
)
from p2p.ecies import generate_privkey

from .cancel_token import CancelTokenFactory
from .kademlia import AddressFactory


class DiscoveryProtocolFactory(factory.Factory):
    class Meta:
        model = DiscoveryProtocol

    privkey = factory.LazyFunction(generate_privkey)
    address = factory.SubFactory(AddressFactory)
    bootstrap_nodes = factory.LazyFunction(tuple)

    cancel_token = factory.SubFactory(CancelTokenFactory, name='discovery-test')

    @classmethod
    def from_seed(cls, seed: bytes, *args: Any, **kwargs: Any) -> DiscoveryProtocol:
        privkey = keys.PrivateKey(keccak(seed))
        return cls(*args, privkey=privkey, **kwargs)


class AuthTagPacketFactory(factory.Factory):
    class Meta:
        model = AuthTagPacket

    tag = b"\x00" * TAG_SIZE
    auth_tag = b"\x00" * NONCE_SIZE
    encrypted_message = b"\x00" * 10


class AuthHeaderFactory(factory.Factory):
    class Meta:
        model = AuthHeader

    auth_tag = b"\x00" * NONCE_SIZE
    id_nonce = b"\x00" * ID_NONCE_SIZE
    auth_scheme_name = AUTH_SCHEME_NAME
    ephemeral_public_key = b"\x00" * 32
    encrypted_auth_response = b"\x00" * 10


class AuthHeaderPacketFactory(factory.Factory):
    class Meta:
        model = AuthHeaderPacket

    tag = b"\x00" * TAG_SIZE
    auth_header = factory.SubFactory(AuthHeaderFactory)
    encrypted_message = b"\x00" * 10


class WhoAreYouPacketFactory(factory.Factory):
    class Meta:
        model = WhoAreYouPacket

    magic = b"\x00" * MAGIC_SIZE
    token = b"\x00" * NONCE_SIZE
    id_nonce = b"\x00" * ID_NONCE_SIZE
    enr_sequence_number = 0


class EndpointFactory(factory.Factory):
    class Meta:
        model = Endpoint

    ip_address = factory.LazyFunction(lambda: socket.inet_aton(factory.Faker("ipv4").generate({})))
    port = factory.Faker("pyint", min_value=0, max_value=65535)


class EndpointVoteFactory(factory.Factory):
    class Meta:
        model = EndpointVote

    endpoint = factory.SubFactory(EndpointFactory)
    node_id = factory.LazyFunction(lambda: ENRFactory().node_id)
    timestamp = factory.Faker("unix_time")


class IncomingPacketFactory(factory.Factory):
    class Meta:
        model = IncomingPacket

    packet = factory.SubFactory(AuthTagPacketFactory)
    sender_endpoint = factory.SubFactory(EndpointFactory)


class NodeIDFactory(factory.Factory):
    class Meta:
        model = NodeID
        inline_args = ("node_id",)

    node_id = factory.Faker("binary", length=32)


class ENRFactory(factory.Factory):
    class Meta:
        model = ENR

    sequence_number = factory.Faker("pyint", min_value=0, max_value=100)
    kv_pairs = factory.LazyAttribute(lambda o: merge({
        b"id": b"v4",
        b"secp256k1": keys.PrivateKey(o.private_key).public_key.to_compressed_bytes(),
    }, o.custom_kv_pairs))
    signature = factory.LazyAttribute(
        lambda o: UnsignedENR(
            o.sequence_number,
            o.kv_pairs,
        ).to_signed_enr(o.private_key).signature
    )

    class Params:
        private_key = factory.Faker("binary", length=V4IdentityScheme.private_key_size)
        custom_kv_pairs: Dict[bytes, Any] = {}


class PingMessageFactory(factory.Factory):
    class Meta:
        model = PingMessage

    request_id = factory.Faker("pyint", min_value=0, max_value=100)
    enr_seq = factory.Faker("pyint", min_value=0, max_value=100)


class HandshakeInitiatorFactory(factory.Factory):
    class Meta:
        model = HandshakeInitiator

    local_private_key = factory.Faker("binary", length=V4IdentityScheme.private_key_size)
    local_enr = factory.LazyAttribute(lambda o: ENRFactory(private_key=o.local_private_key))
    remote_enr = factory.LazyAttribute(lambda o: ENRFactory(private_key=o.remote_private_key))
    initial_message = factory.SubFactory(PingMessageFactory)

    class Params:
        remote_private_key = factory.Faker("binary", length=V4IdentityScheme.private_key_size)


class HandshakeRecipientFactory(factory.Factory):
    class Meta:
        model = HandshakeRecipient

    local_private_key = factory.Faker("binary", length=V4IdentityScheme.private_key_size)
    local_enr = factory.LazyAttribute(lambda o: ENRFactory(private_key=o.local_private_key))
    remote_enr = factory.LazyAttribute(lambda o: ENRFactory(private_key=o.remote_private_key))
    remote_node_id = factory.LazyAttribute(lambda o: o.remote_enr.node_id)
    initiating_packet_auth_tag = factory.Faker("binary", length=NONCE_SIZE)

    class Params:
        remote_private_key = factory.Faker("binary", length=V4IdentityScheme.private_key_size)
