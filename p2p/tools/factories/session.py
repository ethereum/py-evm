import factory

from p2p.session import Session

from .kademlia import NodeFactory


class SessionFactory(factory.Factory):
    class Meta:
        model = Session

    remote = factory.SubFactory(NodeFactory)
    session_id = None
