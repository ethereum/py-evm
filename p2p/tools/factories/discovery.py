import random
import socket
from typing import (
    Any,
    Dict,
    Tuple,
)

import factory

from eth_keys import keys

from eth_utils import (
    big_endian_to_int,
    int_to_big_endian,
    keccak,
)
from eth_utils.toolz import (
    merge,
    reduce,
)

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
    IncomingMessage,
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
    FindNodeMessage,
    PingMessage,
)
from p2p.discv5.handshake import (
    HandshakeInitiator,
    HandshakeRecipient,
)
from p2p.discv5.routing_table import (
    compute_log_distance,
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

    @classmethod
    def at_log_distance(cls, reference: NodeID, log_distance: int) -> NodeID:
        num_bits = len(reference) * 8

        if log_distance >= num_bits:
            raise ValueError("Log distance must be less than number of bits in the node id")
        elif log_distance < 0:
            raise ValueError("Log distance cannot be negative")

        num_common_bits = num_bits - log_distance - 1
        flipped_bit_index = num_common_bits
        num_random_bits = num_bits - num_common_bits - 1

        reference_bits = bytes_to_bits(reference)

        shared_bits = reference_bits[:num_common_bits]
        flipped_bit = not reference_bits[flipped_bit_index]
        random_bits = [
            bool(random.randint(0, 1))
            for _ in range(flipped_bit_index + 1, flipped_bit_index + 1 + num_random_bits)
        ]

        result_bits = tuple(list(shared_bits) + [flipped_bit] + random_bits)
        result = NodeID(bits_to_bytes(result_bits))

        assert compute_log_distance(result, reference) == log_distance
        return result


def bytes_to_bits(input_bytes: bytes) -> Tuple[bool, ...]:
    num_bits = len(input_bytes) * 8
    as_int = big_endian_to_int(input_bytes)
    as_bits = tuple(
        bool(as_int & (1 << index))
        for index in range(num_bits)
    )[::-1]
    return as_bits


def bits_to_bytes(input_bits: Tuple[bool, ...]) -> bytes:
    if len(input_bits) % 8 != 0:
        raise ValueError("Number of input bits must be a multiple of 8")
    num_bytes = len(input_bits) // 8

    as_int = reduce(
        lambda rest, bit: rest * 2 + bit,
        input_bits,
    )
    as_bytes_unpadded = int_to_big_endian(as_int)
    padding = b"\x00" * (num_bytes - len(as_bytes_unpadded))
    return padding + as_bytes_unpadded


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


class FindNodeMessageFactory(factory.Factory):
    class Meta:
        model = FindNodeMessage

    request_id = factory.Faker("pyint", min_value=0, max_value=100)
    distance = factory.Faker("pyint", min_value=0, max_value=32)


class IncomingMessageFactory(factory.Factory):
    class Meta:
        model = IncomingMessage

    message = factory.SubFactory(PingMessageFactory)
    sender_endpoint = factory.SubFactory(EndpointFactory)
    sender_node_id = factory.SubFactory(NodeIDFactory)


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
