from typing import Any

import factory

from p2p.abc import AddressAPI, NodeAPI
from p2p.kademlia import Node, Address

from .keys import PublicKeyFactory
from .socket import get_open_port


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
