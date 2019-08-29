from collections import (
    deque,
)
import logging
import random
from typing import (
    Any,
    Deque,
    Iterator,
    Collection,
)

from eth_utils import (
    encode_hex,
)

from p2p.discv5.typing import (
    NodeID,
)


class FlatRoutingTable(Collection[NodeID]):

    logger = logging.getLogger("p2p.discv5.routing_table_manager.FlatRoutingTable")

    def __init__(self) -> None:
        self.entries: Deque[NodeID] = deque()

    def add(self, node_id: NodeID) -> None:
        if node_id not in self:
            self.logger.debug("Adding entry %s", encode_hex(node_id))
            self.entries.appendleft(node_id)
        else:
            raise ValueError(f"Entry {encode_hex(node_id)} already present in the routing table")

    def update(self, node_id: NodeID) -> None:
        self.remove(node_id)
        self.add(node_id)

    def add_or_update(self, node_id: NodeID) -> None:
        try:
            self.remove(node_id)
        except KeyError:
            pass
        finally:
            self.add(node_id)

    def remove(self, node_id: NodeID) -> None:
        try:
            self.entries.remove(node_id)
        except ValueError:
            raise KeyError(f"Entry {encode_hex(node_id)} not present in the routing table")
        else:
            self.logger.debug("Removing entry %s", encode_hex(node_id))

    def __contains__(self, node_id: Any) -> bool:
        return node_id in self.entries

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[NodeID]:
        return iter(self.entries)

    def get_random_entry(self) -> NodeID:
        return random.choice(self.entries)

    def get_oldest_entry(self) -> NodeID:
        return self.entries[-1]
