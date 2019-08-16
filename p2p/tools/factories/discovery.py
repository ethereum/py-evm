from typing import Any

import factory

from eth_keys import keys

from eth_utils import keccak

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
    ephemeral_pubkey = b"\x00" * 32
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

    ip_address = factory.Faker("ipv4")
    port = factory.Faker("pyint", min_value=0, max_value=65535)
