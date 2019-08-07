import hashlib

from eth_typing import (
    Hash32,
)

from p2p._utils import (
    sxor,
)


def compute_tag(source_node_id: bytes, destination_node_id: bytes) -> Hash32:
    """Compute the tag used in message packets sent between two nodes."""
    destination_node_id_hash = hashlib.sha256(destination_node_id).digest()
    tag = sxor(destination_node_id_hash, source_node_id)
    return Hash32(tag)


def recover_source_id_from_tag(tag: Hash32, destination_node_id: bytes) -> bytes:
    """Recover the node id of the source from the tag in a message packet."""
    destination_node_id_hash = hashlib.sha256(destination_node_id).digest()
    source_node_id = sxor(tag, destination_node_id_hash)
    return source_node_id
