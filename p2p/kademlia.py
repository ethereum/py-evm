import asyncio
import bisect
import collections
import contextlib
from functools import total_ordering
import ipaddress
import logging
import operator
import random
import struct
import time
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    Hashable,
    Iterable,
    Iterator,
    List,
    Set,
    Sized,
    Tuple,
    TYPE_CHECKING,
)
from urllib import parse as urlparse

import cytoolz

from eth_utils import (
    big_endian_to_int,
    decode_hex,
    encode_hex,
)

from eth_keys import (
    datatypes,
    keys,
)

from eth_hash.auto import keccak

from cancel_token import CancelToken

# Workaround for import cycles caused by type annotations:
# http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
if TYPE_CHECKING:
    from p2p.discovery import DiscoveryProtocol  # noqa: F401

    # Promoted workaround for inheriting from generic stdlib class
    # https://github.com/python/mypy/issues/5264#issuecomment-399407428
    UserDict = collections.UserDict[Hashable, 'CallbackLock']
else:
    UserDict = collections.UserDict

k_b = 8  # 8 bits per hop

k_bucket_size = 16
k_request_timeout = 0.9                  # timeout of message round trips
k_idle_bucket_refresh_interval = 3600    # ping all nodes in bucket if bucket was idle
k_find_concurrency = 3                   # parallel find node lookups
k_pubkey_size = 512
k_id_size = 256
k_max_node_id = 2 ** k_id_size - 1


def int_to_big_endian4(integer: int) -> bytes:
    ''' 4 bytes big endian integer'''
    return struct.pack('>I', integer)


def enc_port(p: int) -> bytes:
    return int_to_big_endian4(p)[-2:]


class AlreadyWaiting(Exception):
    pass


class Address:

    def __init__(self, ip: str, udp_port: int, tcp_port: int = 0) -> None:
        tcp_port = tcp_port or udp_port
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        self._ip = ipaddress.ip_address(ip)

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
    def from_endpoint(cls, ip: str, udp_port: str, tcp_port: str = '\x00\x00') -> 'Address':
        return cls(ip, big_endian_to_int(udp_port), big_endian_to_int(tcp_port))


@total_ordering
class Node:

    def __init__(self, pubkey: datatypes.PublicKey, address: Address) -> None:
        self.pubkey = pubkey
        self.address = address
        self.id = big_endian_to_int(keccak(pubkey.to_bytes()))

    @classmethod
    def from_uri(cls, uri: str) -> 'Node':
        parsed = urlparse.urlparse(uri)
        pubkey = keys.PublicKey(decode_hex(parsed.username))
        return cls(pubkey, Address(parsed.hostname, parsed.port))

    def __str__(self) -> str:
        return '<Node(%s@%s)>' % (self.pubkey.to_hex()[:6], self.address.ip)

    def __repr__(self) -> str:
        return '<Node(%s@%s:%d)>' % (self.pubkey.to_hex(), self.address.ip, self.address.tcp_port)

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
        other = cast(Node, other)
        return self.pubkey == other.pubkey

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash(self.pubkey)


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
        self.last_updated = time.time()

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
        self.last_updated = time.time()
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
            raise TypeError("Cannot compare KBucket with type {}.".format(other.__class__))
        return self.end < other.start


class RoutingTable:
    logger = logging.getLogger("p2p.kademlia.RoutingTable")

    def __init__(self, node: Node) -> None:
        self.this_node = node
        self.buckets = [KBucket(0, k_max_node_id)]

    def get_random_nodes(self, count: int) -> Iterator[Node]:
        if count > len(self):
            self.logger.warn(
                "Cannot get %d nodes as RoutingTable contains only %d nodes", count, len(self))
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
        idle_cutoff_time = time.time() - k_idle_bucket_refresh_interval
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
                if n is not node_id:
                    nodes.append(n)
                    if len(nodes) == k * 2:
                        break
        return sort_by_distance(nodes, node_id)[:k]


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
        raise ValueError("No bucket found for node with id {}".format(node.id))


class CallbackLock:
    def __init__(self,
                 callback: Callable[..., Any],
                 timeout: float=2 * k_request_timeout) -> None:
        self.callback = callback
        self.timeout = timeout
        self.created_at = time.time()

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.timeout


class CallbackManager(UserDict):
    @contextlib.contextmanager
    def acquire(self,
                key: Hashable,
                callback: Callable[..., Any]) -> Iterator[CallbackLock]:
        if key in self:
            if not self.locked(key):
                del self[key]
            else:
                raise AlreadyWaiting("Already waiting on callback for: {0}".format(key))

        lock = CallbackLock(callback)
        self[key] = lock

        try:
            yield lock
        finally:
            del self[key]

    def get_callback(self, key: Hashable) -> Callable[..., Any]:
        return self[key].callback

    def locked(self, key: Hashable) -> bool:
        try:
            lock = self[key]
        except KeyError:
            return False
        else:
            if lock.is_expired:
                return False
            else:
                return True


class KademliaProtocol:
    logger = logging.getLogger("p2p.kademlia.KademliaProtocol")

    def __init__(self, node: Node, wire: 'DiscoveryProtocol') -> None:
        self.this_node = node
        self.wire = wire
        self.routing = RoutingTable(node)

        self.pong_callbacks = CallbackManager()
        self.ping_callbacks = CallbackManager()
        self.neighbours_callbacks = CallbackManager()
        self.parity_pong_tokens: Dict[bytes, bytes] = {}

    def recv_neighbours(self, remote: Node, neighbours: List[Node]) -> None:
        """Process a neighbours response.

        Neighbours responses should only be received as a reply to a find_node, and that is only
        done as part of node lookup, so the actual processing is left to the callback from
        neighbours_callbacks, which is added (and removed after it's done or timed out) in
        wait_neighbours().
        """
        self.logger.debug('<<< neighbours from %s: %s', remote, neighbours)
        try:
            callback = self.neighbours_callbacks.get_callback(remote)
        except KeyError:
            self.logger.debug(
                'unexpected neighbours from %s, probably came too late', remote)
        else:
            callback(neighbours)

    def recv_pong(self, remote: Node, token: bytes) -> None:
        """Process a pong packet.

        Pong packets should only be received as a response to a ping, so the actual processing is
        left to the callback from pong_callbacks, which is added (and removed after it's done
        or timed out) in wait_pong().
        """
        # XXX: This hack is needed because there are lots of parity 1.10 nodes out there that send
        # the wrong token on pong msgs (https://github.com/paritytech/parity/issues/8038). We
        # should get rid of this once there are no longer too many parity 1.10 nodes out there.
        if token in self.parity_pong_tokens:
            # This is a pong from a buggy parity node, so need to lookup the actual token we're
            # expecting.
            token = self.parity_pong_tokens.pop(token)
        else:
            # This is a pong from a non-buggy node, so just cleanup self.parity_pong_tokens.
            self.parity_pong_tokens = cytoolz.valfilter(
                lambda val: val != token, self.parity_pong_tokens)

        self.logger.debug('<<< pong from %s (token == %s)', remote, encode_hex(token))
        pingid = self._mkpingid(token, remote)

        try:
            callback = self.pong_callbacks.get_callback(pingid)
        except KeyError:
            self.logger.debug('unexpected pong from %s (token == %s)', remote, encode_hex(token))
        else:
            callback()

    def recv_ping(self, remote: Node, hash_: bytes) -> None:
        """Process a received ping packet.

        A ping packet may come any time, unrequested, or may be prompted by us bond()ing with a
        new node. In the former case we'll just update the sender's entry in our routing table and
        reply with a pong, whereas in the latter we'll also fire a callback from ping_callbacks.
        """
        self.logger.debug('<<< ping from %s', remote)
        if remote == self.this_node:
            self.logger.info('Invariant: received ping from this_node: %s', remote)
            return
        else:
            self.update_routing_table(remote)
        self.wire.send_pong(remote, hash_)
        # Sometimes a ping will be sent to us as part of the bonding
        # performed the first time we see a node, and it is in those cases that
        # a callback will exist.
        try:
            callback = self.ping_callbacks.get_callback(remote)
        except KeyError:
            pass
        else:
            callback()

    def recv_find_node(self, remote: Node, targetid: int) -> None:
        if remote not in self.routing:
            # FIXME: This is not correct; a node we've bonded before may have become unavailable
            # and thus removed from self.routing, but once it's back online we should accept
            # find_nodes from them.
            self.logger.debug('Ignoring find_node request from unknown node %s', remote)
            return
        self.update_routing_table(remote)
        found = self.routing.neighbours(targetid)
        self.wire.send_neighbours(remote, found)

    def update_routing_table(self, node: Node) -> None:
        """Update the routing table entry for the given node."""
        eviction_candidate = self.routing.add_node(node)
        if eviction_candidate:
            # This means we couldn't add the node because its bucket is full, so schedule a bond()
            # with the least recently seen node on that bucket. If the bonding fails the node will
            # be removed from the bucket and a new one will be picked from the bucket's
            # replacement cache.
            asyncio.ensure_future(self.bond(eviction_candidate, self.wire.cancel_token))

    async def wait_ping(self, remote: Node, cancel_token: CancelToken) -> bool:
        """Wait for a ping from the given remote.

        This coroutine adds a callback to ping_callbacks and yields control until that callback is
        called or a timeout (k_request_timeout) occurs. At that point it returns whether or not
        a ping was received from the given node.
        """
        event = asyncio.Event()

        with self.ping_callbacks.acquire(remote, event.set):
            got_ping = False
            try:
                got_ping = await cancel_token.cancellable_wait(
                    event.wait(), timeout=k_request_timeout)
                self.logger.debug('got expected ping from %s', remote)
            except TimeoutError:
                self.logger.debug('timed out waiting for ping from %s', remote)

        return got_ping

    async def wait_pong(self, remote: Node, token: bytes, cancel_token: CancelToken) -> bool:
        """Wait for a pong from the given remote containing the given token.

        This coroutine adds a callback to pong_callbacks and yields control until that callback is
        called or a timeout (k_request_timeout) occurs. At that point it returns whether or not
        a pong was received with the given pingid.
        """
        pingid = self._mkpingid(token, remote)
        event = asyncio.Event()

        with self.pong_callbacks.acquire(pingid, event.set):
            got_pong = False
            try:
                got_pong = await cancel_token.cancellable_wait(
                    event.wait(), timeout=k_request_timeout)
                self.logger.debug('got expected pong with token %s', encode_hex(token))
            except TimeoutError:
                self.logger.debug(
                    'timed out waiting for pong from %s (token == %s)',
                    remote,
                    encode_hex(token),
                )

        return got_pong

    async def wait_neighbours(self, remote: Node, cancel_token: CancelToken) -> Tuple[Node, ...]:
        """Wait for a neihgbours packet from the given node.

        Returns the list of neighbours received.
        """
        event = asyncio.Event()
        neighbours: List[Node] = []

        def process(response: List[Node]) -> None:
            neighbours.extend(response)
            # This callback is expected to be called multiple times because nodes usually
            # split the neighbours replies into multiple packets, so we only call event.set() once
            # we've received enough neighbours.
            if len(neighbours) == k_bucket_size:
                event.set()

        with self.neighbours_callbacks.acquire(remote, process):
            try:
                await cancel_token.cancellable_wait(
                    event.wait(), timeout=k_request_timeout)
                self.logger.debug('got expected neighbours response from %s', remote)
            except TimeoutError:
                self.logger.debug('timed out waiting for neighbours response from %s', remote)

        return tuple(n for n in neighbours if n != self.this_node)

    def ping(self, node: Node) -> bytes:
        if node == self.this_node:
            raise ValueError("Cannot ping self")
        return self.wire.send_ping(node)

    async def bond(self, node: Node, cancel_token: CancelToken) -> bool:
        """Bond with the given node.

        Bonding consists of pinging the node, waiting for a pong and maybe a ping as well.
        It is necessary to do this at least once before we send find_node requests to a node.
        """
        if node in self.routing:
            return True
        elif node == self.this_node:
            return False

        token = self.ping(node)

        try:
            got_pong = await self.wait_pong(node, token, cancel_token)
        except AlreadyWaiting:
            self.logger.debug("binding failed, already waiting for pong")
            return False

        if not got_pong:
            self.logger.debug("bonding failed, didn't receive pong from %s", node)
            self.routing.remove_node(node)
            return False

        try:
            # Give the remote node a chance to ping us before we move on and
            # start sending find_node requests. It is ok for wait_ping() to
            # timeout and return false here as that just means the remote
            # remembers us.
            await self.wait_ping(node, cancel_token)
        except AlreadyWaiting:
            self.logger.debug("binding failed, already waiting for ping")
            return False

        self.logger.debug("bonding completed successfully with %s", node)
        self.update_routing_table(node)
        return True

    async def bootstrap(self, bootstrap_nodes: Iterable[Node], cancel_token: CancelToken) -> None:
        bonded = await asyncio.gather(*(
            self.bond(n, cancel_token)
            for n
            in bootstrap_nodes
            if (not self.ping_callbacks.locked(n) and not self.pong_callbacks.locked(n))
        ))
        if not any(bonded):
            self.logger.info("Failed to bond with bootstrap nodes %s", bootstrap_nodes)
            return
        await self.lookup_random(cancel_token)

    async def lookup(self, node_id: int, cancel_token: CancelToken) -> List[Node]:
        """Lookup performs a network search for nodes close to the given target.

        It approaches the target by querying nodes that are closer to it on each iteration.  The
        given target does not need to be an actual node identifier.
        """
        nodes_asked: Set[Node] = set()
        nodes_seen: Set[Node] = set()

        async def _find_node(node_id: int, remote: Node) -> Tuple[Node, ...]:
            # Short-circuit in case our token has been triggered to avoid trying to send requests
            # over a transport that is probably closed already.
            cancel_token.raise_if_triggered()
            self.wire.send_find_node(remote, node_id)
            candidates = await self.wait_neighbours(remote, cancel_token)
            if not candidates:
                self.logger.debug("got no candidates from %s, returning", remote)
                return tuple()
            all_candidates = tuple(c for c in candidates if c not in nodes_seen)
            candidates = tuple(
                c for c in all_candidates
                if (not self.ping_callbacks.locked(c) and not self.pong_callbacks.locked(c))
            )
            self.logger.debug("got %s new candidates", len(candidates))
            # Add new candidates to nodes_seen so that we don't attempt to bond with failing ones
            # in the future.
            nodes_seen.update(candidates)
            bonded = await asyncio.gather(*(self.bond(c, cancel_token) for c in candidates))
            self.logger.debug("bonded with %s candidates", bonded.count(True))
            return tuple(c for c in candidates if bonded[candidates.index(c)])

        def _exclude_if_asked(nodes: Iterable[Node]) -> List[Node]:
            nodes_to_ask = list(set(nodes).difference(nodes_asked))
            return sort_by_distance(nodes_to_ask, node_id)[:k_find_concurrency]

        closest = self.routing.neighbours(node_id)
        self.logger.debug("starting lookup; initial neighbours: %s", closest)
        nodes_to_ask = _exclude_if_asked(closest)
        while nodes_to_ask:
            self.logger.debug("node lookup; querying %s", nodes_to_ask)
            nodes_asked.update(nodes_to_ask)
            results = await asyncio.gather(*(
                _find_node(node_id, n)
                for n
                in nodes_to_ask
                if not self.neighbours_callbacks.locked(n)
            ))
            for candidates in results:
                closest.extend(candidates)
            closest = sort_by_distance(closest, node_id)[:k_bucket_size]
            nodes_to_ask = _exclude_if_asked(closest)

        self.logger.debug("lookup finished for %s: %s", node_id, closest)
        return closest

    async def lookup_random(self, cancel_token: CancelToken) -> List[Node]:
        return await self.lookup(random.randint(0, k_max_node_id), cancel_token)

    # TODO: Run this as a coroutine that loops forever and after each iteration sleeps until the
    # time when the least recently touched bucket will be considered idle.
    def refresh_idle_buckets(self) -> None:
        # For buckets that haven't been touched in 3600 seconds, pick a random value in the bucket's
        # range and perform discovery for that value.
        for bucket in self.routing.idle_buckets:
            rid = random.randint(bucket.start, bucket.end)
            asyncio.ensure_future(self.lookup(rid, self.wire.cancel_token))

    def _mkpingid(self, token: bytes, node: Node) -> bytes:
        return token + node.pubkey.to_bytes()

    async def populate_not_full_buckets(self) -> None:
        """Go through all buckets that are not full and try to fill them.

        For every node in the replacement cache of every non-full bucket, try to bond.
        When the bonding succeeds the node is automatically added to the bucket.
        """
        for bucket in self.routing.not_full_buckets:
            for node in bucket.replacement_cache:
                asyncio.ensure_future(self.bond(node, self.wire.cancel_token))


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
