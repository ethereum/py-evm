import factory

from libp2p.security.insecure_security import (
    InsecureTransport,
)

from trinity.protocol.bcc_libp2p.configs import (
    SECURITY_PROTOCOL_ID,
    MULTIPLEXING_PROTOCOL_ID,
)

from p2p.ecies import (
    generate_privkey,
)
from p2p.tools.factories import (
    get_open_port,
)

from .node import (
    Node,
)


class NodeFactory(factory.Factory):
    class Meta:
        model = Node

    privkey = factory.LazyFunction(generate_privkey)
    listen_ip = "127.0.0.1"
    listen_port = factory.LazyFunction(get_open_port)
    security_protocol_ops = {SECURITY_PROTOCOL_ID: InsecureTransport("plaintext")}
    muxer_protocol_ids = [MULTIPLEXING_PROTOCOL_ID]
