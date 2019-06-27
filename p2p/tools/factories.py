import random
import socket
from typing import Any, Tuple

from cancel_token import CancelToken

from eth_utils import (
    keccak,
    int_to_big_endian,
)

from eth_keys import datatypes
from eth_keys import keys

from p2p import discovery
from p2p import kademlia
from p2p.ecies import generate_privkey
from p2p.tools.memory_transport import MemoryTransport


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


class CancelTokenFactory(factory.Factory):
    class Meta:
        model = CancelToken

    name = factory.Sequence(lambda n: "test-token-%d".format(n))


class DiscoveryProtocolFactory(factory.Factory):
    class Meta:
        model = discovery.DiscoveryProtocol

    privkey = factory.LazyFunction(generate_privkey)
    address = factory.SubFactory(AddressFactory)
    bootstrap_nodes = factory.LazyFunction(tuple)

    cancel_token = factory.SubFactory(CancelTokenFactory, name='discovery-test')

    @classmethod
    def from_seed(cls, seed: bytes, *args: Any, **kwargs: Any) -> discovery.DiscoveryProtocol:
        privkey = keys.PrivateKey(keccak(seed))
        return cls(*args, privkey=privkey, **kwargs)


def MemoryTransportPairFactory(alice_remote: kademlia.Node = None,
                               alice_private_key: datatypes.PrivateKey = None,
                               alice_token: CancelToken = None,
                               bob_remote: kademlia.Node = None,
                               bob_private_key: datatypes.PrivateKey = None,
                               bob_token: CancelToken = None,
                               ) -> Tuple[MemoryTransport, MemoryTransport]:
    if alice_remote is None:
        alice_remote = NodeFactory()
    if alice_private_key is None:
        alice_private_key = PrivateKeyFactory()
    if alice_token is None:
        alice_token = CancelTokenFactory(name='alice')

    if bob_remote is None:
        bob_remote = NodeFactory()
    if bob_private_key is None:
        bob_private_key = PrivateKeyFactory()
    if bob_token is None:
        bob_token = CancelTokenFactory(name='bob')

    # the remotes are intentionally switched since they represent the *other*
    # side of the connection.
    alice_transport, bob_transport = MemoryTransport.connected_pair(
        alice=(bob_remote, alice_private_key, alice_token),
        bob=(alice_remote, bob_private_key, bob_token),
    )
    return alice_transport, bob_transport
