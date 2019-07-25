from typing import (
    Any,
    Tuple,
)

from libp2p.security.insecure_security import (
    InsecureTransport,
)

from trinity.protocol.bcc_libp2p.configs import (
    SECURITY_PROTOCOL_ID,
    MULTIPLEXING_PROTOCOL_ID,
)
from trinity.protocol.bcc_libp2p.node import (
    Node,
)

from p2p.ecies import (
    generate_privkey,
)
from p2p.tools.factories import (
    get_open_port,
)

try:
    import factory
except ImportError:
    raise ImportError("The trinity.tools.factories module requires the `factory_boy` library.")


class NodeFactory(factory.Factory):
    class Meta:
        model = Node

    privkey = factory.LazyFunction(generate_privkey)
    listen_ip = "127.0.0.1"
    listen_port = factory.LazyFunction(get_open_port)
    security_protocol_ops = {SECURITY_PROTOCOL_ID: InsecureTransport("plaintext")}
    muxer_protocol_ids = (MULTIPLEXING_PROTOCOL_ID,)
    gossipsub_params = None
    cancel_token = None
    bootstrap_nodes = None
    preferred_nodes = None

    @classmethod
    def create_batch(cls, number: int) -> Tuple[Node, ...]:
        return tuple(
            cls() for _ in range(number)
        )

    @classmethod
    def with_args(cls, *args: Any, **kwargs: Any) -> Node:
        return cls(*args, **kwargs)
