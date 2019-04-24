import pickle

from p2p.tools.factories import NodeFactory


def test_kademlia_node_is_pickleable():
    node = NodeFactory()
    result = pickle.loads(pickle.dumps(node))
    assert result == node
