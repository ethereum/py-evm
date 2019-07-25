import asyncio
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

from p2p import auth
from p2p import discovery
from p2p.abc import AddressAPI, NodeAPI, TransportAPI
from p2p.ecies import generate_privkey
from p2p.kademlia import Node, Address
from p2p.transport import Transport

from p2p.tools.memory_transport import MemoryTransport
from p2p.tools.asyncio_streams import get_directly_connected_streams


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
        model = Address

    ip = factory.Sequence(lambda n: f'10.{(n // 65536) % 256}.{(n // 256) % 256}.{n % 256}')
    udp_port = factory.LazyFunction(get_open_port)
    tcp_port = 0

    @classmethod
    def localhost(cls, *args: Any, **kwargs: Any) -> AddressAPI:
        return cls(*args, ip='127.0.0.1', **kwargs)


class NodeFactory(factory.Factory):
    class Meta:
        model = Node

    pubkey = factory.LazyFunction(PublicKeyFactory)
    address = factory.SubFactory(AddressFactory)

    @classmethod
    def with_nodeid(cls, nodeid: int, *args: Any, **kwargs: Any) -> NodeAPI:
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


async def TransportPairFactory(*,
                               alice_remote: NodeAPI = None,
                               alice_private_key: keys.PrivateKey = None,
                               bob_remote: NodeAPI = None,
                               bob_private_key: keys.PrivateKey = None,
                               token: CancelToken = None,
                               use_eip8: bool = False,
                               ) -> Tuple[TransportAPI, TransportAPI]:
    if token is None:
        token = CancelTokenFactory(name='TransportPairFactory')

    if alice_private_key is None:
        alice_private_key = PrivateKeyFactory()
    if alice_remote is None:
        alice_remote = NodeFactory(pubkey=alice_private_key.public_key)

    if bob_private_key is None:
        bob_private_key = PrivateKeyFactory()
    if bob_remote is None:
        bob_remote = NodeFactory(pubkey=bob_private_key.public_key)

    assert alice_private_key.public_key == alice_remote.pubkey
    assert bob_private_key.public_key == bob_remote.pubkey
    assert alice_private_key != bob_private_key

    initiator = auth.HandshakeInitiator(bob_remote, alice_private_key, use_eip8, token)

    f_alice: 'asyncio.Future[TransportAPI]' = asyncio.Future()
    handshake_finished = asyncio.Event()

    bob_peername = (bob_remote.address.ip, bob_remote.address.udp_port, bob_remote.address.tcp_port)
    alice_peername = (alice_remote.address.ip, alice_remote.address.udp_port, alice_remote.address.tcp_port)  # noqa: E501

    (
        (alice_reader, alice_writer),
        (bob_reader, bob_writer),
    ) = get_directly_connected_streams(
        bob_extra_info={'peername': bob_peername},
        alice_extra_info={'peername': alice_peername},
    )

    async def establish_transport() -> None:
        aes_secret, mac_secret, egress_mac, ingress_mac = await auth._handshake(
            initiator, alice_reader, alice_writer, token)

        transport = Transport(
            remote=alice_remote,
            private_key=alice_private_key,
            reader=alice_reader,
            writer=alice_writer,
            aes_secret=aes_secret,
            mac_secret=mac_secret,
            egress_mac=egress_mac,
            ingress_mac=ingress_mac,
        )

        f_alice.set_result(transport)
        handshake_finished.set()

    asyncio.ensure_future(establish_transport())

    bob_transport = await asyncio.wait_for(Transport.receive_connection(
        reader=bob_reader,
        writer=bob_writer,
        private_key=bob_private_key,
        token=token,
    ), timeout=1)

    await asyncio.wait_for(handshake_finished.wait(), timeout=0.1)
    alice_transport = await asyncio.wait_for(f_alice, timeout=0.1)
    return alice_transport, bob_transport


def MemoryTransportPairFactory(alice_remote: NodeAPI = None,
                               alice_private_key: datatypes.PrivateKey = None,
                               bob_remote: NodeAPI = None,
                               bob_private_key: datatypes.PrivateKey = None,
                               ) -> Tuple[TransportAPI, TransportAPI]:
    if alice_remote is None:
        alice_remote = NodeFactory()
    if alice_private_key is None:
        alice_private_key = PrivateKeyFactory()

    if bob_remote is None:
        bob_remote = NodeFactory()
    if bob_private_key is None:
        bob_private_key = PrivateKeyFactory()

    # the remotes are intentionally switched since they represent the *other*
    # side of the connection.
    alice_transport, bob_transport = MemoryTransport.connected_pair(
        alice=(bob_remote, alice_private_key),
        bob=(alice_remote, bob_private_key),
    )
    return alice_transport, bob_transport
