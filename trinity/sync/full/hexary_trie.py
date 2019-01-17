import bisect
from typing import (
    Awaitable,
    Callable,
    Dict,
    List,
    Tuple,
)

from eth_utils import (
    encode_hex,
)

from eth_typing import (
    Hash32
)

from eth.db.backends.base import BaseDB
from eth.tools.logging import ExtendedDebugLogger

from trie.constants import (
    NODE_TYPE_BLANK,
    NODE_TYPE_BRANCH,
    NODE_TYPE_EXTENSION,
    NODE_TYPE_LEAF,
)
from trie.utils.nodes import (
    decode_node,
    get_node_type,
    is_blank_node,
)

from trinity.db.base import BaseAsyncDB
from trinity.exceptions import SyncRequestAlreadyProcessed


class SyncRequest:

    def __init__(
            self, node_key: Hash32, parent: 'SyncRequest', depth: int,
            leaf_callback: Callable[[bytes, 'SyncRequest'], Awaitable[None]],
            is_raw: bool = False) -> None:
        """Create a new SyncRequest for a given HexaryTrie node.

        :param node_key: The node's key.
        :param parent: The node's parent.
        :param depth: The ndoe's depth in the trie.
        :param leaf_callback: A callback called when for all leaf children of this node.
        :param is_raw: If True, HexaryTrieSync will simply store the node's data in the db,
        without decoding and scheduling requests for children. This is needed to fetch contract
        code when doing a state sync.
        """
        self.node_key = node_key
        self.parents: List[SyncRequest] = []
        if parent is not None:
            self.parents = [parent]
        self.depth = depth
        self.leaf_callback = leaf_callback
        self.is_raw = is_raw
        self.dependencies = 0
        self.data: bytes = None

    def __lt__(self, other: 'SyncRequest') -> bool:
        return self.depth < other.depth

    def __repr__(self) -> str:
        return "SyncRequest(%s, depth=%d)" % (encode_hex(self.node_key), self.depth)


def _get_children(node: Hash32, depth: int
                  ) -> Tuple[List[Tuple[int, Hash32]], List[bytes]]:
    """Return all children of the node with the given hash.

    :rtype: A two-tuple with one list containing the children that reference other nodes and
    another containing the leaf children.
    """
    node_type = get_node_type(node)
    references = []
    leaves = []

    if node_type == NODE_TYPE_BLANK:
        pass
    elif node_type == NODE_TYPE_LEAF:
        leaves.append(node[1])
    elif node_type == NODE_TYPE_EXTENSION:
        if isinstance(node[1], bytes) and len(node[1]) == 32:
            references.append((depth + 1, Hash32(node[1])))
        elif isinstance(node[1], list):
            # the rlp encoding of the node is < 32 so rather than a 32-byte
            # reference, the actual rlp encoding of the node is inlined.
            sub_references, sub_leaves = _get_children(node[1], depth + 1)
            references.extend(sub_references)
            leaves.extend(sub_leaves)
        else:
            raise Exception("Invariant")
    elif node_type == NODE_TYPE_BRANCH:
        for sub_node in node[:16]:
            if isinstance(sub_node, bytes) and len(sub_node) == 32:
                # this is a reference to another node.
                references.append((depth + 1, sub_node))
            else:
                # TODO: Follow up on mypy confusion around `int`, `bytes` and `Hash32` here
                sub_references, sub_leaves = _get_children(sub_node, depth)  # type: ignore
                references.extend(sub_references)
                leaves.extend(sub_leaves)  # type: ignore

        # The last item in a branch may contain a value.
        if not is_blank_node(node[16]):
            leaves.append(node[16])

    return references, leaves  # type: ignore


class HexaryTrieSync:

    def __init__(self,
                 root_hash: Hash32,
                 db: BaseAsyncDB,
                 nodes_cache: BaseDB,
                 logger: ExtendedDebugLogger) -> None:
        # Nodes that haven't been requested yet.
        self.queue: List[SyncRequest] = []
        # Nodes that have been requested to a peer, but not yet committed to the DB, either
        # because we haven't processed a reply containing them or because some of their children
        # haven't been retrieved/committed yet.
        self.requests: Dict[Hash32, SyncRequest] = {}
        self.db = db
        self.root_hash = root_hash
        self.logger = logger
        # A cache of node hashes we know to exist in our DB, used to avoid querying the DB
        # unnecessarily as that's the main bottleneck when dealing with a large DB like for
        # ethereum's mainnet/ropsten.
        self.nodes_cache = nodes_cache
        self.committed_nodes = 0
        if root_hash in self.db:
            self.logger.info("Root node (%s) already exists in DB, nothing to do", root_hash)
        else:
            self._schedule(root_hash, parent=None, depth=0, leaf_callback=self.leaf_callback)

    async def leaf_callback(self, data: bytes, parent: SyncRequest) -> None:
        """Called when we reach a leaf node.

        Should be implemented by subclasses that need to perform special handling of leaves.
        """
        pass

    @property
    def has_pending_requests(self) -> bool:
        return len(self.requests) > 0

    def next_batch(self, n: int = 1) -> List[SyncRequest]:
        """Return the next requests that should be dispatched."""
        if len(self.queue) == 0:
            return []
        batch = list(reversed((self.queue[-n:])))
        self.queue = self.queue[:-n]
        return batch

    async def schedule(self, node_key: Hash32, parent: SyncRequest, depth: int,
                       leaf_callback: Callable[[bytes, 'SyncRequest'], Awaitable[None]],
                       is_raw: bool = False) -> None:
        """Schedule a request for the node with the given key."""
        if node_key in self.nodes_cache:
            self.logger.debug2("Node %s already exists in db", encode_hex(node_key))
            return
        if await self.db.coro_exists(node_key):
            self.nodes_cache[node_key] = b''
            self.logger.debug2("Node %s already exists in db", encode_hex(node_key))
            return
        self._schedule(node_key, parent, depth, leaf_callback, is_raw)

    def _schedule(self, node_key: Hash32, parent: SyncRequest, depth: int,
                  leaf_callback: Callable[[bytes, 'SyncRequest'], Awaitable[None]],
                  is_raw: bool = False) -> None:
        if parent is not None:
            parent.dependencies += 1

        existing = self.requests.get(node_key)
        if existing is not None:
            self.logger.debug2(
                "Already requesting %s, will just update parents list", node_key)
            existing.parents.append(parent)
            return

        request = SyncRequest(node_key, parent, depth, leaf_callback, is_raw)
        # Requests get added to both self.queue and self.requests; the former is used to keep
        # track which requests should be sent next, and the latter is used to avoid scheduling a
        # request for a given node multiple times.
        self.logger.debug2("Scheduling retrieval of %s", encode_hex(request.node_key))
        self.requests[request.node_key] = request
        bisect.insort(self.queue, request)

    async def process(self, results: List[Tuple[Hash32, bytes]]) -> None:
        """Process request results.

        :param results: A list of two-tuples containing the node's key and data.
        """
        for node_key, data in results:
            request = self.requests.get(node_key)
            if request is None:
                # This may happen if we resend a request for a node after waiting too long,
                # and then eventually get two responses with it.
                self.logger.debug2(
                    "No SyncRequest found for %s, maybe we got more than one response for it",
                    encode_hex(node_key))
                return

            if request.data is not None:
                raise SyncRequestAlreadyProcessed("%s has been processed already" % request)

            request.data = data
            if request.is_raw:
                await self.commit(request)
                continue

            node = decode_node(request.data)
            references, leaves = _get_children(node, request.depth)

            for depth, ref in references:
                await self.schedule(ref, request, depth, request.leaf_callback)

            if request.leaf_callback is not None:
                for leaf in leaves:
                    await request.leaf_callback(leaf, request)

            if request.dependencies == 0:
                await self.commit(request)

    async def commit(self, request: SyncRequest) -> None:
        """Commit the given request's data to the database.

        The request's data attribute must be set (done by the process() method) before this can be
        called.
        """
        self.committed_nodes += 1
        await self.db.coro_set(request.node_key, request.data)
        self.nodes_cache[request.node_key] = b''
        self.requests.pop(request.node_key)
        for ancestor in request.parents:
            ancestor.dependencies -= 1
            if ancestor.dependencies == 0:
                await self.commit(ancestor)
