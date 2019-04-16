import random
import socket
from typing import Any

from cancel_token import CancelToken

from eth_utils import (
    keccak,
    int_to_big_endian,
)

from eth_keys import keys

from p2p import discovery
from p2p import kademlia
from p2p.ecies import generate_privkey


try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")


def get_open_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


def PrivateKeyFactory(seed: bytes=None) -> keys.PrivateKey:
    if seed is None:
        key_bytes = int_to_big_endian(random.getrandbits(256)).rjust(32, b'\x00')
    else:
        key_bytes = keccak(seed)
    return keys.PrivateKey(key_bytes)


def PublicKeyFactory() -> keys.PublicKey:
    return PrivateKeyFactory().public_key


class AddressFactory(factory.Factory):
    class Meta:
        model = kademlia.Address

    ip = factory.Sequence(lambda n: f'10.{(n // 65536) % 256}.{(n // 256) % 256}.{n % 256}')
    udp_port = factory.LazyFunction(get_open_port)
    tcp_port = 0

    @classmethod
    def localhost(cls, *args: Any, **kwargs: Any) -> kademlia.Address:
        return cls(*args, ip='127.0.0.1', **kwargs)


class NodeFactory(factory.Factory):
    class Meta:
        model = kademlia.Node

    pubkey = factory.LazyFunction(PublicKeyFactory)
    address = factory.SubFactory(AddressFactory)

    @classmethod
    def with_nodeid(cls, nodeid: int, *args: Any, **kwargs: Any) -> kademlia.Node:
        node = cls(*args, **kwargs)
        node.id = nodeid
        return node


class DiscoveryProtocolFactory(factory.Factory):
    class Meta:
        model = discovery.DiscoveryProtocol

    privkey = factory.LazyFunction(generate_privkey)
    address = factory.SubFactory(AddressFactory)
    bootstrap_nodes = factory.LazyFunction(tuple)
    cancel_token = factory.LazyFunction(lambda: CancelToken('discovery-test'))

    @classmethod
    def from_seed(cls, seed: bytes, *args: Any, **kwargs: Any) -> discovery.DiscoveryProtocol:
        privkey = keys.PrivateKey(keccak(seed))
        return cls(*args, privkey=privkey, **kwargs)
