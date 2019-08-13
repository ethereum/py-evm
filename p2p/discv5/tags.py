import hashlib

from p2p._utils import (
    sxor,
)

from p2p.discv5.typing import (
    NodeID,
    Tag,
)


def compute_tag(source_node_id: NodeID, destination_node_id: NodeID) -> Tag:
    """Compute the tag used in message packets sent between two nodes."""
    destination_node_id_hash = hashlib.sha256(destination_node_id).digest()
    tag = sxor(destination_node_id_hash, source_node_id)
    return Tag(tag)


def recover_source_id_from_tag(tag: Tag, destination_node_id: NodeID) -> NodeID:
    """Recover the node id of the source from the tag in a message packet."""
    destination_node_id_hash = hashlib.sha256(destination_node_id).digest()
    source_node_id = sxor(tag, destination_node_id_hash)
    return NodeID(source_node_id)
