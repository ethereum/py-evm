import collections
import functools
import itertools
import logging
import secrets
from typing import (
    Any,
    Generator,
    Collection,
    Deque,
    Iterator,
    Tuple,
)

from eth_utils import (
    big_endian_to_int,
    encode_hex,
)

from p2p.discv5.constants import (
    NUM_ROUTING_TABLE_BUCKETS,
)
from p2p.discv5.typing import (
    NodeID,
)


class FlatRoutingTable(Collection[NodeID]):

    logger = logging.getLogger("p2p.discv5.routing_table_manager.FlatRoutingTable")

    def __init__(self) -> None:
        self.entries: Deque[NodeID] = collections.deque()

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
        return secrets.choice(self.entries)

    def get_oldest_entry(self) -> NodeID:
        return self.entries[-1]


def compute_distance(left_node_id: NodeID, right_node_id: NodeID) -> int:
    left_int = big_endian_to_int(left_node_id)
    right_int = big_endian_to_int(right_node_id)
    return left_int ^ right_int


def compute_log_distance(left_node_id: NodeID, right_node_id: NodeID) -> int:
    if left_node_id == right_node_id:
        raise ValueError("Cannot compute log distance between identical nodes")
    distance = compute_distance(left_node_id, right_node_id)
    return distance.bit_length() - 1


class KademliaRoutingTable:
    logger = logging.getLogger("p2p.discv5.routing_table.KademliaRoutingTable")

    def __init__(self, center_node_id: NodeID, bucket_size: int) -> None:
        self.center_node_id = center_node_id
        self.bucket_size = bucket_size

        self.buckets: Tuple[Deque[NodeID], ...] = tuple(
            collections.deque(maxlen=bucket_size) for _ in range(NUM_ROUTING_TABLE_BUCKETS)
        )
        self.replacement_caches: Tuple[Deque[NodeID], ...] = tuple(
            collections.deque() for _ in range(NUM_ROUTING_TABLE_BUCKETS)
        )

        self.bucket_update_order: Deque[int] = collections.deque()

    def get_index_bucket_and_replacement_cache(self,
                                               node_id: NodeID,
                                               ) -> Tuple[int, Deque[NodeID], Deque[NodeID]]:
        index = compute_log_distance(self.center_node_id, node_id)
        bucket = self.buckets[index]
        replacement_cache = self.replacement_caches[index]
        return index, bucket, replacement_cache

    def update(self, node_id: NodeID) -> NodeID:
        """Insert a node into the routing table or move it to the top if already present.

        If the bucket is already full, the node id will be added to the replacement cache and
        the oldest node is returned as an eviction candidate. Otherwise, the return value is
        `None`.
        """
        if node_id == self.center_node_id:
            raise ValueError("Cannot insert center node into routing table")

        bucket_index, bucket, replacement_cache = self.get_index_bucket_and_replacement_cache(
            node_id,
        )

        is_bucket_full = len(bucket) >= self.bucket_size
        is_node_in_bucket = node_id in bucket

        if not is_node_in_bucket and not is_bucket_full:
            self.logger.debug("Adding %s to bucket %d", encode_hex(node_id), bucket_index)
            self.update_bucket_unchecked(node_id)
            eviction_candidate = None
        elif is_node_in_bucket:
            self.logger.debug("Updating %s in bucket %d", encode_hex(node_id), bucket_index)
            self.update_bucket_unchecked(node_id)
            eviction_candidate = None
        elif not is_node_in_bucket and is_bucket_full:
            if node_id not in replacement_cache:
                self.logger.debug(
                    "Adding %s to replacement cache of bucket %d",
                    encode_hex(node_id),
                    bucket_index,
                )
            else:
                self.logger.debug(
                    "Updating %s in replacement cache of bucket %d",
                    encode_hex(node_id),
                    bucket_index,
                )
                replacement_cache.remove(node_id)
            replacement_cache.appendleft(node_id)
            eviction_candidate = bucket[-1]
        else:
            raise Exception("unreachable")

        return eviction_candidate

    def update_bucket_unchecked(self, node_id: NodeID) -> None:
        """Add or update assuming the node is either present already or the bucket is not full."""
        bucket_index, bucket, replacement_cache = self.get_index_bucket_and_replacement_cache(
            node_id,
        )

        for container in (bucket, replacement_cache):
            try:
                container.remove(node_id)
            except ValueError:
                pass
        bucket.appendleft(node_id)

        try:
            self.bucket_update_order.remove(bucket_index)
        except ValueError:
            pass
        self.bucket_update_order.appendleft(bucket_index)

    def remove(self, node_id: NodeID) -> None:
        """Remove a node from the routing table if it is present.

        If possible, the node will be replaced with the newest entry in the replacement cache.
        """
        bucket_index, bucket, replacement_cache = self.get_index_bucket_and_replacement_cache(
            node_id,
        )

        in_bucket = node_id in bucket
        in_replacement_cache = node_id in replacement_cache

        if in_bucket:
            bucket.remove(node_id)
            if replacement_cache:
                replacement_node_id = replacement_cache.popleft()
                self.logger.debug(
                    "Replacing %s from bucket %d with %s from replacement cache",
                    encode_hex(node_id),
                    bucket_index,
                    encode_hex(replacement_node_id),
                )
                bucket.append(replacement_node_id)
            else:
                self.logger.debug(
                    "Removing %s from bucket %d without replacement",
                    encode_hex(node_id),
                    bucket_index,
                )

        if in_replacement_cache:
            self.logger.debug(
                "Removing %s from replacement cache of bucket %d",
                encode_hex(node_id),
                bucket_index,
            )
            replacement_cache.remove(node_id)

        if not in_bucket and not in_replacement_cache:
            self.logger.debug(
                "Not removing %s as it is neither present in the bucket nor the replacement cache",
                encode_hex(node_id),
                bucket_index,
            )

        # bucket_update_order should only contain non-empty buckets, so remove it if necessary
        if not bucket:
            try:
                self.bucket_update_order.remove(bucket_index)
            except ValueError:
                pass

    def get_nodes_at_log_distance(self, log_distance: int) -> Tuple[NodeID, ...]:
        """Get all nodes in the routing table at the given log distance to the center."""
        if log_distance < 0:
            raise ValueError("Log distance must not be negative")
        elif log_distance >= len(self.buckets):
            raise ValueError(f"Log distance must be smaller than {len(self.buckets)}")
        return tuple(self.buckets[log_distance])

    @property
    def is_empty(self) -> bool:
        return all(len(bucket) == 0 for bucket in self.buckets)

    def get_least_recently_updated_log_distance(self) -> int:
        """Get the log distance whose corresponding bucket was updated least recently.

        Only non-empty buckets are considered. If all buckets are empty, a `ValueError` is raised.
        """
        try:
            bucket_index = self.bucket_update_order[-1]
        except IndexError:
            raise ValueError("Routing table is empty")
        else:
            return bucket_index

    def iter_nodes_around(self, reference_node_id: NodeID) -> Generator[NodeID, None, None]:
        """Iterate over all nodes in the routing table ordered by distance to a given reference."""
        all_node_ids = itertools.chain(*self.buckets)
        distance_to_reference = functools.partial(compute_distance, reference_node_id)
        sorted_node_ids = sorted(all_node_ids, key=distance_to_reference)
        for node_id in sorted_node_ids:
            yield node_id
