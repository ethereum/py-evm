import asyncio
import itertools
import random
import socket
from typing import Any, Callable, Generator, Iterable, Tuple, Type

from cancel_token import CancelToken

from rlp import sedes

from eth_utils import (
    keccak,
    int_to_big_endian,
    to_tuple,
)

from eth_keys import keys

from p2p import auth
from p2p import discovery
from p2p.abc import AddressAPI, NodeAPI, ProtocolAPI, TransportAPI, MultiplexerAPI
from p2p.ecies import generate_privkey
from p2p.kademlia import Node, Address
from p2p.multiplexer import Multiplexer
from p2p.p2p_proto import P2PProtocol
from p2p.protocol import Command, Protocol, get_cmd_offsets
from p2p.transport import Transport

from p2p.tools.asyncio_streams import get_directly_connected_streams
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
                               alice_private_key: keys.PrivateKey = None,
                               bob_remote: NodeAPI = None,
                               bob_private_key: keys.PrivateKey = None,
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


STRUCTURE_SEDES = (
    sedes.big_endian_int,
    sedes.binary,
)


@to_tuple
def StructureFactory(high_water_mark: int = 4,
                     ) -> Iterable[Tuple[str, Any]]:
    for idx in range(high_water_mark):
        name = f"field_{idx}"
        sedes = random.choice(STRUCTURE_SEDES)
        yield (name, sedes)
        if random.randrange(idx, high_water_mark + 2) >= high_water_mark:
            break


ACTIONS = (
    'dig',
    'run',
    'jump',
    'create',
    'destroy',
    'fill',
    'build',
    'create',
    'kill',
    'finish',
    'hello',
    'goodbye',
    'connect',
    'disconnect',
    'activate',
    'disable',
    'enable',
    'validate',
    'post',
    'get',
)


ANIMALS = (
    'dog',
    'cat',
    'bird',
    'fox',
    'panda',
    'unicorn',
    'bear',
    'eagle',
)


COLORS = (
    'red',
    'orange',
    'yellow',
    'green',
    'blue',
    'purple',
    'pink',
    'brown',
    'black',
    'white',
)


def _command_name_enumerator() -> Generator[str, None, None]:
    while True:
        for action in ACTIONS:
            yield action.title()
        for action, animal in itertools.product(ACTIONS, ANIMALS):
            yield f"{action.title()}{animal.title()}"


_command_name_iter = _command_name_enumerator()


def CommandNameFactory() -> str:
    return next(_command_name_iter)


def CommandFactory(name: str = None,
                   cmd_id: int = None,
                   structure: Tuple[Tuple[str, Any], ...] = None) -> Type[Command]:
    if structure is None:
        structure = StructureFactory()
    if cmd_id is None:
        cmd_id = 0
    if name is None:
        name = CommandNameFactory()

    return type(
        name,
        (Command,),
        {'_cmd_id': cmd_id, 'structure': structure},
    )


def _protocol_name_enumerator() -> Generator[str, None, None]:
    while True:
        for color, animal in itertools.product(COLORS, ANIMALS):
            yield f"{color}_{animal}"


_protocol_name_iter = _protocol_name_enumerator()


def ProtocolNameFactory() -> str:
    return next(_protocol_name_iter)


def ProtocolFactory(name: str = None,
                    version: int = None,
                    commands: Tuple[Type[Command], ...] = None) -> Type[Protocol]:
    if name is None:
        name = ProtocolNameFactory()
    if version is None:
        version = 1
    if commands is None:
        num_commands = random.randrange(1, 6)
        commands = tuple(
            CommandFactory(cmd_id=cmd_id)
            for cmd_id in range(num_commands)
        )

    cmd_length = len(commands)

    return type(
        name.title(),
        (Protocol,),
        {'name': name, 'version': version, '_commands': commands, 'cmd_length': cmd_length},
    )


TransportPair = Tuple[
    TransportAPI,
    TransportAPI,
]


def MultiplexerPairFactory(*,
                           protocol_types: Tuple[Type[ProtocolAPI], ...] = (),
                           transport_factory: Callable[..., TransportPair] = MemoryTransportPairFactory,  # noqa: E501
                           alice_remote: NodeAPI = None,
                           alice_private_key: keys.PrivateKey = None,
                           bob_remote: NodeAPI = None,
                           bob_private_key: keys.PrivateKey = None,
                           snappy_support: bool = False,
                           cancel_token: CancelToken = None,
                           ) -> Tuple[MultiplexerAPI, MultiplexerAPI]:
    alice_transport, bob_transport = transport_factory(
        alice_remote=alice_remote,
        alice_private_key=alice_private_key,
        bob_remote=bob_remote,
        bob_private_key=bob_private_key,
    )
    cmd_id_offsets = get_cmd_offsets(protocol_types)
    alice_protocols = tuple(
        protocol_class(alice_transport, offset, snappy_support)
        for protocol_class, offset
        in zip(protocol_types, cmd_id_offsets)
    )
    bob_protocols = tuple(
        protocol_class(bob_transport, offset, snappy_support)
        for protocol_class, offset
        in zip(protocol_types, cmd_id_offsets)
    )

    alice_p2p_protocol = P2PProtocol(alice_transport, snappy_support)
    alice_multiplexer = Multiplexer(
        transport=alice_transport,
        base_protocol=alice_p2p_protocol,
        protocols=alice_protocols,
        token=cancel_token,
    )

    bob_p2p_protocol = P2PProtocol(bob_transport, False)
    bob_multiplexer = Multiplexer(
        transport=bob_transport,
        base_protocol=bob_p2p_protocol,
        protocols=bob_protocols,
        token=cancel_token,
    )
    return alice_multiplexer, bob_multiplexer
