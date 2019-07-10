import bisect
from functools import total_ordering
import ipaddress
import logging
import operator
import random
import struct
import time
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Sized,
    Tuple,
)
from urllib import parse as urlparse

from eth_utils import (
    big_endian_to_int,
    decode_hex,
    remove_0x_prefix,
)

from eth_keys import (
    datatypes,
    keys,
)

from eth_hash.auto import keccak

from p2p.validation import validate_enode_uri

k_b = 8  # 8 bits per hop

k_bucket_size = 16
k_request_timeout = 7.2                  # timeout of message round trips
k_idle_bucket_refresh_interval = 3600    # ping all nodes in bucket if bucket was idle
k_find_concurrency = 3                   # parallel find node lookups
k_pubkey_size = 512
k_id_size = 256
k_max_node_id = 2 ** k_id_size - 1


def int_to_big_endian4(integer: int) -> bytes:
    """ 4 bytes big endian integer"""
    return struct.pack('>I', integer)


def enc_port(p: int) -> bytes:
    return int_to_big_endian4(p)[-2:]


class Address:

    def __init__(self, ip: str, udp_port: int, tcp_port: int = 0) -> None:
        tcp_port = tcp_port or udp_port
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        self._ip = ipaddress.ip_address(ip)

    @property
    def is_loopback(self) -> bool:
        return self._ip.is_loopback

    @property
    def is_unspecified(self) -> bool:
        return self._ip.is_unspecified

    @property
    def is_reserved(self) -> bool:
        return self._ip.is_reserved

    @property
    def is_private(self) -> bool:
        return self._ip.is_private

    @property
    def ip(self) -> str:
        return str(self._ip)

    def __eq__(self, other: Any) -> bool:
        return (self.ip, self.udp_port) == (other.ip, other.udp_port)

    def __repr__(self) -> str:
        return 'Address(%s:udp:%s|tcp:%s)' % (self.ip, self.udp_port, self.tcp_port)

    def to_endpoint(self) -> List[bytes]:
        return [self._ip.packed, enc_port(self.udp_port), enc_port(self.tcp_port)]

    @classmethod
    def from_endpoint(cls, ip: str, udp_port: bytes, tcp_port: bytes = b'\x00\x00') -> 'Address':
        return cls(ip, big_endian_to_int(udp_port), big_endian_to_int(tcp_port))


@total_ordering
class Node:

    def __init__(self, pubkey: datatypes.PublicKey, address: Address) -> None:
        self.pubkey = pubkey
        self.address = address
        self.id = big_endian_to_int(keccak(pubkey.to_bytes()))

    @classmethod
    def from_uri(cls, uri: str) -> 'Node':
        validate_enode_uri(uri)  # Be no more permissive than the validation
        parsed = urlparse.urlparse(uri)
        pubkey = keys.PublicKey(decode_hex(parsed.username))
        return cls(pubkey, Address(parsed.hostname, parsed.port))

    def uri(self) -> str:
        hexstring = self.pubkey.to_hex()
        hexstring = remove_0x_prefix(hexstring)
        return f'enode://{hexstring}@{self.address.ip}:{self.address.tcp_port}'

    def __str__(self) -> str:
        return f"<Node({self.pubkey.to_hex()[:6]}@{self.address.ip})>"

    def __repr__(self) -> str:
        return f"<Node({self.pubkey.to_hex()}@{self.address.ip}:{self.address.tcp_port})>"

    def distance_to(self, id: int) -> int:
        return self.id ^ id

    # mypy doesn't have support for @total_ordering
    # https://github.com/python/mypy/issues/4610
    def __lt__(self, other: 'Node') -> bool:
        if not isinstance(other, self.__class__):
            return super().__lt__(other)  # type: ignore
        return self.id < other.id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return super().__eq__(other)
        return self.pubkey == other.pubkey

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash(self.pubkey)

    def __getstate__(self) -> Dict[Any, Any]:
        return {'enode': self.uri()}

    def __setstate__(self, state: Dict[Any, Any]) -> None:
        enode = state.pop('enode')
        node = self.from_uri(enode)
        self.__dict__.update(node.__dict__)


@total_ordering
class KBucket(Sized):
    """A bucket of nodes whose IDs fall between the bucket's start and end.

    The bucket is kept sorted by time last seen—least-recently seen node at the head,
    most-recently seen at the tail.
    """
    k = k_bucket_size

    def __init__(self, start: int, end: int) -> None:
        self.start = start
        self.end = end
        self.nodes: List[Node] = []
        self.replacement_cache: List[Node] = []
        self.last_updated = time.monotonic()

    @property
    def midpoint(self) -> int:
        return self.start + (self.end - self.start) // 2

    def distance_to(self, id: int) -> int:
        return self.midpoint ^ id

    def nodes_by_distance_to(self, id: int) -> List[Node]:
        return sorted(self.nodes, key=operator.methodcaller('distance_to', id))

    def split(self) -> Tuple['KBucket', 'KBucket']:
        """Split at the median id"""
        splitid = self.midpoint
        lower = KBucket(self.start, splitid)
        upper = KBucket(splitid + 1, self.end)
        for node in self.nodes:
            bucket = lower if node.id <= splitid else upper
            bucket.add(node)
        for node in self.replacement_cache:
            bucket = lower if node.id <= splitid else upper
            bucket.replacement_cache.append(node)
        return lower, upper

    def remove_node(self, node: Node) -> None:
        if node not in self:
            return
        self.nodes.remove(node)
        if self.replacement_cache:
            replacement_node = self.replacement_cache.pop()
            self.nodes.append(replacement_node)

    def in_range(self, node: Node) -> bool:
        return self.start <= node.id <= self.end

    @property
    def is_full(self) -> bool:
        return len(self) == self.k

    def add(self, node: Node) -> Node:
        """Try to add the given node to this bucket.

        If the node is already present, it is moved to the tail of the list, and we return None.

        If the node is not already present and the bucket has fewer than k entries, it is inserted
        at the tail of the list, and we return None.

        If the bucket is full, we add the node to the bucket's replacement cache and return the
        node at the head of the list (i.e. the least recently seen), which should be evicted if it
        fails to respond to a ping.
        """
        self.last_updated = time.monotonic()
        if node in self.nodes:
            self.nodes.remove(node)
            self.nodes.append(node)
        elif len(self) < self.k:
            self.nodes.append(node)
        else:
            self.replacement_cache.append(node)
            return self.head
        return None

    @property
    def head(self) -> Node:
        """Least recently seen"""
        return self.nodes[0]

    def __contains__(self, node: Node) -> bool:
        return node in self.nodes

    def __len__(self) -> int:
        return len(self.nodes)

    def __lt__(self, other: 'KBucket') -> bool:
        if not isinstance(other, self.__class__):
            raise TypeError(f"Cannot compare KBucket with type {other.__class__}")
        return self.end < other.start


class RoutingTable:
    logger = logging.getLogger("p2p.kademlia.RoutingTable")

    def __init__(self, node: Node) -> None:
        self._initialized_at = time.monotonic()
        self.this_node = node
        self.buckets = [KBucket(0, k_max_node_id)]

    def get_random_nodes(self, count: int) -> Iterator[Node]:
        if count > len(self):
            if time.monotonic() - self._initialized_at > 30:
                self.logger.warning(
                    "Cannot get %d nodes as RoutingTable contains only %d nodes",
                    count,
                    len(self),
                )
            count = len(self)
        seen: List[Node] = []
        # This is a rather inneficient way of randomizing nodes from all buckets, but even if we
        # iterate over all nodes in the routing table, the time it takes would still be
        # insignificant compared to the time it takes for the network roundtrips when connecting
        # to nodes.
        while len(seen) < count:
            bucket = random.choice(self.buckets)
            if not bucket.nodes:
                continue
            node = random.choice(bucket.nodes)
            if node not in seen:
                yield node
                seen.append(node)

    def split_bucket(self, index: int) -> None:
        bucket = self.buckets[index]
        a, b = bucket.split()
        self.buckets[index] = a
        self.buckets.insert(index + 1, b)

    @property
    def idle_buckets(self) -> List[KBucket]:
        idle_cutoff_time = time.monotonic() - k_idle_bucket_refresh_interval
        return [b for b in self.buckets if b.last_updated < idle_cutoff_time]

    @property
    def not_full_buckets(self) -> List[KBucket]:
        return [b for b in self.buckets if not b.is_full]

    def remove_node(self, node: Node) -> None:
        binary_get_bucket_for_node(self.buckets, node).remove_node(node)

    def add_node(self, node: Node) -> Node:
        if node == self.this_node:
            raise ValueError("Cannot add this_node to routing table")
        bucket = binary_get_bucket_for_node(self.buckets, node)
        eviction_candidate = bucket.add(node)
        if eviction_candidate is not None:  # bucket is full
            # Split if the bucket has the local node in its range or if the depth is not congruent
            # to 0 mod k_b
            depth = _compute_shared_prefix_bits(bucket.nodes)
            if bucket.in_range(self.this_node) or (depth % k_b != 0 and depth != k_id_size):
                self.split_bucket(self.buckets.index(bucket))
                return self.add_node(node)  # retry
            # Nothing added, ping eviction_candidate
            return eviction_candidate
        return None  # successfully added to not full bucket

    def get_bucket_for_node(self, node: Node) -> KBucket:
        return binary_get_bucket_for_node(self.buckets, node)

    def buckets_by_distance_to(self, id: int) -> List[KBucket]:
        return sorted(self.buckets, key=operator.methodcaller('distance_to', id))

    def __contains__(self, node: Node) -> bool:
        return node in self.get_bucket_for_node(node)

    def __len__(self) -> int:
        return sum(len(b) for b in self.buckets)

    def __iter__(self) -> Iterable[Node]:
        for b in self.buckets:
            for n in b.nodes:
                yield n

    def neighbours(self, node_id: int, k: int = k_bucket_size) -> List[Node]:
        """Return up to k neighbours of the given node."""
        nodes = []
        # Sorting by bucket.midpoint does not work in edge cases, so build a short list of k * 2
        # nodes and sort it by distance_to.
        for bucket in self.buckets_by_distance_to(node_id):
            for n in bucket.nodes_by_distance_to(node_id):
                if n.id is not node_id:
                    nodes.append(n)
                    if len(nodes) == k * 2:
                        break
        return sort_by_distance(nodes, node_id)[:k]


def check_relayed_addr(sender: Address, addr: Address) -> bool:
    """Check if an address relayed by the given sender is valid.

    Reserved and unspecified addresses are always invalid.
    Private addresses are valid if the sender is a private host.
    Loopback addresses are valid if the sender is a loopback host.
    All other addresses are valid.
    """
    if addr.is_unspecified or addr.is_reserved:
        return False
    if addr.is_private and not sender.is_private:
        return False
    if addr.is_loopback and not sender.is_loopback:
        return False
    return True


def binary_get_bucket_for_node(buckets: List[KBucket], node: Node) -> KBucket:
    """Given a list of ordered buckets, returns the bucket for a given node."""
    bucket_ends = [bucket.end for bucket in buckets]
    bucket_position = bisect.bisect_left(bucket_ends, node.id)
    # Prevents edge cases where bisect_left returns an out of range index
    try:
        bucket = buckets[bucket_position]
        assert bucket.start <= node.id <= bucket.end
        return bucket
    except (IndexError, AssertionError):
        raise ValueError(f"No bucket found for node with id {node.id}")


def _compute_shared_prefix_bits(nodes: List[Node]) -> int:
    """Count the number of prefix bits shared by all nodes."""
    def to_binary(x: int) -> str:  # left padded bit representation
        b = bin(x)[2:]
        return '0' * (k_id_size - len(b)) + b

    if len(nodes) < 2:
        return k_id_size

    bits = [to_binary(n.id) for n in nodes]
    for i in range(1, k_id_size + 1):
        if len(set(b[:i] for b in bits)) != 1:
            return i - 1
    # This means we have at least two nodes with the same ID, so raise an AssertionError
    # because we don't want it to be caught accidentally.
    raise AssertionError("Unable to calculate number of shared prefix bits")


def sort_by_distance(nodes: List[Node], target_id: int) -> List[Node]:
    return sorted(nodes, key=operator.methodcaller('distance_to', target_id))
