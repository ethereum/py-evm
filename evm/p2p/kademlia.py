"""
Node discovery and network formation are implemented via a kademlia-like protocol.
The major differences are that packets are signed, node ids are the public keys, and
DHT-related features are excluded. The FIND_VALUE and STORE packets are not implemented.
The parameters necessary to implement the protocol are a
bucket size of 16 (denoted k in Kademlia),
concurrency of 3 (denoted alpha in Kademlia),
and 8 bits per hop (denoted b in Kademlia) for routing.
The eviction check interval is 75 milliseconds,
request timeouts are 300ms, and
the idle bucket-refresh interval is 3600 seconds.

Aside from the previously described exclusions, node discovery closely follows system
and protocol described by Maymounkov and Mazieres.
"""
import operator
import random
import time
from functools import total_ordering

from rlp.utils import is_integer, str_to_bytes

from evm.utils.keccak import keccak
from evm.utils.numeric import big_endian_to_int

# TODO: Setup a logger using the standard logging module.
from structlog import get_logger
log = get_logger()

k_b = 8  # 8 bits per hop

k_bucket_size = 16
k_request_timeout = 3 * 300 / 1000.      # timeout of message round trips
k_idle_bucket_refresh_interval = 3600    # ping all nodes in bucket if bucket was idle
k_find_concurrency = 3                   # parallel find node lookups
k_pubkey_size = 512
k_id_size = 256
k_max_node_id = 2 ** k_id_size - 1


def random_nodeid():
    return random.randint(0, k_max_node_id)


@total_ordering
class Node(object):

    def __init__(self, pubkey):
        self.pubkey = pubkey
        if k_id_size == 512:
            self.id = big_endian_to_int(pubkey)
        else:
            assert k_id_size == 256
            self.id = big_endian_to_int(keccak(pubkey))

    def id_distance(self, id):
        return self.id ^ id

    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            return super(Node, self).__lt__(other)
        return self.id < other.id

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return super(Node, self).__eq__(other)
        return self.pubkey == other.pubkey

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.pubkey)


class KBucket(object):
    """
    Each k-bucket is kept sorted by time last seen—least-recently seen node at the head,
    most-recently seen at the tail. For small values of i, the k-buckets will generally
    be empty (as no appropriate nodes will exist). For large values of i, the lists can
    grow up to size k, where k is a system-wide replication parameter.
    k is chosen such that any given k nodes are very unlikely to fail within an hour of
    each other (for example k = 20).
    """
    k = k_bucket_size

    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.nodes = []
        self.replacement_cache = []
        self.last_updated = time.time()

    @property
    def midpoint(self):
        return self.start + (self.end - self.start) // 2

    def id_distance(self, id):
        return self.midpoint ^ id

    def nodes_by_id_distance(self, id):
        return sorted(self.nodes, key=operator.methodcaller('id_distance', id))

    def split(self):
        """Split at the median id"""
        splitid = self.midpoint
        lower = KBucket(self.start, splitid)
        upper = KBucket(splitid + 1, self.end)
        for node in self.nodes:
            bucket = lower if node.id <= splitid else upper
            bucket.add_node(node)
        for node in self.replacement_cache:
            bucket = lower if node.id <= splitid else upper
            bucket.replacement_cache.append(node)
        return lower, upper

    def remove_node(self, node):
        if node not in self.nodes:
            return
        self.nodes.remove(node)

    def in_range(self, node):
        return self.start <= node.id <= self.end

    @property
    def is_full(self):
        return len(self) == self.k

    def add_node(self, node):
        """
        If the sending node already exists in the recipient’s k-bucket,
        the recipient moves it to the tail of the list.

        If the node is not already in the appropriate k-bucket and the bucket has fewer than k
        entries, then the recipient just inserts the new sender at the tail of the list.

        If the  appropriate k-bucket is full, however, then the recipient pings the k-bucket’s
        least-recently seen node to decide what to do.

        on success: return None
        on bucket full: return least recently seen Node for eviction check
        """
        self.last_updated = time.time()
        if node in self.nodes:  # already exists
            self.nodes.remove(node)
            self.nodes.append(node)
        elif len(self) < self.k:  # add if fewer than k entries
            self.nodes.append(node)
        else:  # bucket is full
            return self.head

    @property
    def head(self):
        """Least recently seen"""
        return self.nodes[0]

    @property
    def depth(self):
        """Depth is the prefix shared by all nodes in the bucket.

        i.e. The number of shared leading bits.
        """
        def to_binary(x):  # left padded bit representation
            b = bin(x)[2:]
            return '0' * (k_id_size - len(b)) + b

        if len(self.nodes) < 2:
            return k_id_size

        bits = [to_binary(n.id) for n in self.nodes]
        for i in range(1, k_id_size + 1):
            if len(set(b[:i] for b in bits)) != 1:
                return i - 1
        # This means we have at least two nodes with the same ID, so raise an AssertionError
        # because we don't want it to be caught accidentally.
        raise AssertionError("Unable to calculate depth")

    def __contains__(self, node):
        return node in self.nodes

    def __len__(self):
        return len(self.nodes)


class RoutingTable():

    def __init__(self, node):
        self.this_node = node
        self.buckets = [KBucket(0, k_max_node_id)]

    def split_bucket(self, bucket):
        a, b = bucket.split()
        index = self.buckets.index(bucket)
        self.buckets[index] = a
        self.buckets.insert(index + 1, b)

    @property
    def idle_buckets(self):
        one_hour_ago = time.time() - k_idle_bucket_refresh_interval
        return [b for b in self.buckets if b.last_updated < one_hour_ago]

    @property
    def not_full_buckets(self):
        return [b for b in self.buckets if len(b) < k_bucket_size]

    def remove_node(self, node):
        self.bucket_by_node(node).remove_node(node)

    def add_node(self, node):
        if node == self.this_node:
            raise ValueError("Cannot add this_node to routing table")
        bucket = self.bucket_by_node(node)
        eviction_candidate = bucket.add_node(node)
        if eviction_candidate is not None:  # bucket is full
            # Split if the bucket has the local node in its range or if the depth is not congruent
            # to 0 mod k_b
            depth = bucket.depth
            if bucket.in_range(self.this_node) or (depth % k_b != 0 and depth != k_id_size):
                self.split_bucket(bucket)
                return self.add_node(node)  # retry
            # Nothing added, ping eviction_candidate
            return eviction_candidate
        return None  # successfully added to not full bucket

    def bucket_by_node(self, node):
        for bucket in self.buckets:
            if node.id < bucket.end:
                assert node.id >= bucket.start
                return bucket
        raise ValueError("No bucket found for node with id {}".format(node.id))

    def buckets_by_id_distance(self, id):
        return sorted(self.buckets, key=operator.methodcaller('id_distance', id))

    def __contains__(self, node):
        return node in self.bucket_by_node(node)

    def __len__(self):
        return sum(len(b) for b in self.buckets)

    def __iter__(self):
        for b in self.buckets:
            for n in b.nodes:
                yield n

    def neighbours(self, nodeid, k=k_bucket_size):
        """Return up to k neighbours of the given node."""
        nodes = []
        # Sorting by bucket.midpoint does not work in edge cases, so build a short list of k * 2
        # nodes and sort it by id_distance.
        for bucket in self.buckets_by_id_distance(nodeid):
            for n in bucket.nodes_by_id_distance(nodeid):
                if n is not nodeid:
                    nodes.append(n)
                    if len(nodes) == k * 2:
                        break
        return sorted(nodes, key=operator.methodcaller('id_distance', nodeid))[:k]


class KademliaProtocol():

    def __init__(self, node, wire):
        self.this_node = node
        self.wire = wire
        self.routing = RoutingTable(node)
        self._expected_pongs = dict()  # pingid -> (timeout, node, replacement_node)
        self._find_requests = dict()  # nodeid -> timeout

    def bootstrap(self, nodes):
        for node in nodes:
            if node == self.this_node:
                continue
            self.routing.add_node(node)
            self.find_node(self.this_node.id, via_node=node)

    def update(self, node, pingid=None):
        """
        When a Kademlia node receives any message (request or reply) from another node,
        it updates the appropriate k-bucket for the sender’s node ID.

        If the sending node already exists in the recipient’s k-bucket, the recipient moves it to
        the tail of the list.

        If the node is not already in the appropriate k-bucket and the bucket has fewer than k
        entries, then the recipient just inserts the new sender at the tail of the list.

        If the appropriate k-bucket is full, however, then the recipient pings the k-bucket’s
        least-recently seen node to decide what to do.

        If the least-recently seen node fails to respond, it is evicted from the k-bucket and the
        new sender inserted at the tail.

        Otherwise, if the least-recently seen node responds, it is moved to the tail of the list,
        and the new sender’s contact is discarded.

        k-buckets effectively implement a least-recently seen eviction policy, except that live
        nodes are never removed from the list.
        """
        if node == self.this_node:
            return

        if pingid is not None and (pingid not in self._expected_pongs):
            return

        # Check for timed out pings and eventually evict them
        for _pingid, (timeout, _node, replacement) in list(self._expected_pongs.items()):
            if time.time() > timeout:
                log.debug('evicting expected pong', remote=_node)
                del self._expected_pongs[_pingid]
                self.routing.remove_node(_node)
                if replacement:
                    self.update(replacement)
                    # XXX (gsalgado): Not sure it's correct to return here?
                    return
                if _node == node:
                    # Prevent node from being added later.
                    # XXX (gsalgado): Not sure it's correct to return here?
                    return

        # if we had registered this node for eviction test
        if pingid in self._expected_pongs:
            timeout, _node, replacement = self._expected_pongs[pingid]
            if replacement:
                # FIXME (gsalgado): Instead of directly accessing the bucket's replacement cache
                # we should have an API for that.
                self.routing.bucket_by_node(replacement).replacement_cache.append(replacement)
            del self._expected_pongs[pingid]

        eviction_candidate = self.routing.add_node(node)
        if eviction_candidate:
            self.ping(eviction_candidate, replacement=node)

        # Check for not full buckets and ping replacements
        for bucket in self.routing.not_full_buckets:
            for node in bucket.replacement_cache:
                self.ping(node)

        # For buckets that haven't been touched in 3600 seconds, pick a random value in the bucket's
        # range and perform discovery for that value.
        for bucket in self.routing.idle_buckets:
            rid = random.randint(bucket.start, bucket.end)
            self.find_node(rid)

        # Check and removed timed out find requests
        self._find_requests = {
            nodeid: timeout
            for nodeid, timeout in self._find_requests.items()
            if time.time() <= timeout
        }

    def _mkpingid(self, echoed, node):
        pid = str_to_bytes(echoed) + node.pubkey
        return pid

    def ping(self, node, replacement=None):
        """
        successful pings should lead to an update
        if bucket is not full
        elif least recently seen, does not respond in time
        """
        assert isinstance(node, Node)
        assert node != self.this_node
        echoed = self.wire.send_ping(node)
        pingid = self._mkpingid(echoed, node)
        assert pingid
        timeout = time.time() + k_request_timeout
        self._expected_pongs[pingid] = (timeout, node, replacement)

    def recv_ping(self, remote, echo):
        "udp addresses determined by socket address of revd Ping packets"  # ok
        "tcp addresses determined by contents of Ping packet"  # not yet
        log.debug('<<< ping', node=remote)
        assert isinstance(remote, Node)
        if remote == self.this_node:
            return
        self.update(remote)
        self.wire.send_pong(remote, echo)

    def recv_pong(self, remote, echoed):
        "tcp addresses are only updated upon receipt of Pong packet"
        log.debug('<<< pong', remoteid=remote)
        assert remote != self.this_node
        pingid = self._mkpingid(echoed, remote)
        # FIXME: This method is called from DiscoveryProtocol, so it is usually passed a
        # discovery.Node instance, and this is ensuring that is really the case before attempting
        # to update the node's address. Maybe we should add the .address field to kademlia.Node
        if hasattr(remote, 'address'):
            nnodes = self.routing.neighbours(remote)
            if nnodes and nnodes[0] == remote:
                nnodes[0].address = remote.address  # updated tcp address
        # update rest
        self.update(remote, pingid)

    def _query_neighbours(self, targetid):
        for n in self.routing.neighbours(targetid)[:k_find_concurrency]:
            self.wire.send_find_node(n, targetid)

    def find_node(self, targetid, via_node=None):
        # FIXME, amplification attack (need to ping pong ping pong first)
        assert is_integer(targetid)
        assert not via_node or isinstance(via_node, Node)
        self._find_requests[targetid] = time.time() + k_request_timeout
        if via_node:
            self.wire.send_find_node(via_node, targetid)
        else:
            self._query_neighbours(targetid)
        # FIXME, should we return the closest node (allow callbacks on find_request)

    def recv_neighbours(self, remote, neighbours):
        """
        if one of the neighbours is closer than the closest known neighbour
            if not timed out
                query closest node for neighbours
        add all nodes to the list
        """
        log.debug('<<< neighbours', remoteid=remote, neighbours=neighbours)
        assert isinstance(neighbours, list)
        neighbours = [n for n in neighbours if n != self.this_node]
        neighbours = [n for n in neighbours if n not in self.routing]

        # we don't map requests to responses, thus forwarding to all FIXME
        for nodeid, timeout in self._find_requests.items():
            assert is_integer(nodeid)
            closest = sorted(neighbours, key=operator.methodcaller('id_distance', nodeid))
            if time.time() < timeout:
                closest_known = self.routing.neighbours(nodeid)
                closest_known = closest_known[0] if closest_known else None
                assert closest_known != self.this_node
                # send find_node requests to k_find_concurrency closests
                for close_node in closest[:k_find_concurrency]:
                    if not closest_known or \
                            close_node.id_distance(nodeid) < closest_known.id_distance(nodeid):
                        self.wire.send_find_node(close_node, nodeid)

        # add all nodes to the list
        for node in neighbours:
            if node != self.this_node:
                self.ping(node)

    def recv_find_node(self, remote, targetid):
        # FIXME, amplification attack (need to ping pong ping pong first)
        assert isinstance(remote, Node)
        assert is_integer(targetid)
        self.update(remote)
        found = self.routing.neighbours(targetid)
        self.wire.send_neighbours(remote, found)
