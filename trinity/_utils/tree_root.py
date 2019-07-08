from typing import (
    Dict,
    Generic,
    Optional,
    Tuple,
    TypeVar,
)
from eth_utils import ValidationError

TNodeID = TypeVar('TNodeID')


class Tree(Generic[TNodeID]):
    """
    A graph built by adding nodes which only know their parents. Each node
    must have exactly one parent, but it need not be present at insertion time.

    Because the Tree is built out-of-order, it may actually be a forest of trees
    at any time.

    Nodes can only be removed if their parent is not present
    """
    def __init__(self) -> None:
        self._parents: Dict[TNodeID, TNodeID] = {}
        self._children: Dict[TNodeID, Tuple[TNodeID, ...]] = {}

    def has_node(self, node_id: TNodeID) -> bool:
        return node_id in self._parents

    def has_parent(self, node_id: TNodeID) -> bool:
        return self.has_node(node_id) and self.has_node(self._parents[node_id])

    def parent_of(self, node_id: TNodeID) -> TNodeID:
        parent = self._parents[node_id]
        if self.has_node(parent):
            parent_children = self.children_of(parent)
            if node_id not in parent_children:
                raise ValidationError(
                    f"Node {node_id} has parent {parent}, but the parent only has children "
                    f"{parent_children}, not the original node."
                )

        return parent

    def children_of(self, node_id: TNodeID) -> Tuple[TNodeID, ...]:
        return self._children.get(node_id, tuple())

    def add(self, node_id: TNodeID, parent_id: TNodeID) -> None:
        if self.has_node(node_id):
            raise ValidationError(f"must not re-add same node twice: {node_id}")
        else:
            self._parents[node_id] = parent_id
            children = self._children.get(parent_id, tuple())
            self._children[parent_id] = children + (node_id, )

    def prune(self, node_id: TNodeID) -> None:
        if self.has_parent(node_id):
            raise ValidationError(
                f"must not prune a node {node_id} that has a parent {self.parent_of(node_id)}"
            )
        else:
            parent_id = self._parents.pop(node_id)

            # remove node ID from parent's children
            parent_children = self.children_of(parent_id)
            new_parent_children = tuple(child for child in parent_children if child != node_id)
            if len(new_parent_children):
                self._children[parent_id] = new_parent_children
            else:
                del self._children[parent_id]


class TreeRoot(Generic[TNodeID]):
    """
    This class tracks the root of a node in a tree (the node with no parents).
    The root may be extended to recursively point to the eventual "true" root.

    A key point is that the root is mutable. In this way, when a node is pruned,
    all the children nodes that point to the root are updated at once, by updating
    this single tree root.

    The tree root extends in two cases:
        - the root node was added before its parent, OR
        - the root node is known to be a fork from its parent at addition time

    Why is it important for these to be extensions, instead of updating the root node
    to the new root?
        - When a root node is added before its parent, the depths to the true root are
        unknown, so the extension provides the opportunity to modify the offset to account
        for the new depth.
        - When a root node is a known fork, it is important to be able to mutate the root
        for one side of the fork, and then mutate the root for the other side of the fork,
        with distinct root objects.
    """
    def __init__(self, root_node_id: TNodeID) -> None:
        # _root_id is the best-known root node at the time of node insertion
        self._root_id = root_node_id
        self._depth_offset = 0
        self._extends_root: Optional[TreeRoot[TNodeID]] = None
        self._depth_extension: Optional[int] = None

    @property
    def _is_extension(self) -> bool:
        return self._extends_root is not None

    def extend(self, tree_root: 'TreeRoot[TNodeID]', more_depth: int) -> None:
        """
        Indicate that what was once the original root now has a new root, because
        a parent node was added. tree_root is the new root node, and more_depth
        is how much deeper the new root is beyond the current root.
        """
        if self._is_extension:
            raise ValidationError("Cannot extend a node that is already extended...")
        self._depth_extension = more_depth
        self._extends_root = tree_root

    def _prune(self, from_node: TNodeID, to_node: TNodeID, old_depth_offset: int) -> None:
        """
        Meant for pruning one node at a time
        """
        if self._is_extension:
            if self._extends_root._is_extension:
                raise ValidationError(
                    f"Cannot prune extension whose target {self._extends_root} is an extension"
                )
            else:
                if to_node != self._root_id:
                    raise ValidationError(
                        f"Cannot prune an extension node to {to_node}, must prune to "
                        f"its non-extension target: {self._root_id}"
                    )
                self._extends_root = None
                self._depth_offset = old_depth_offset - 1 + self._depth_extension
        else:
            if from_node != self._root_id:
                raise ValidationError(f"Pruned node {from_node} must be root: {self._root_id}")
            elif old_depth_offset != self._depth_offset:
                raise ValidationError(
                    f"Trying to prune child node with unexpected offset: {old_depth_offset} "
                    f"instead of expected {self._depth_offset}"
                )
            else:
                self._depth_offset -= 1
                self._root_id = to_node

    def prune_to(self, child_pairs: Tuple[Tuple[TNodeID, 'TreeRoot[TNodeID]'], ...]) -> None:
        """
        Prune the root, to each of the children provided. Each child pair is the new
        node ID for the child and the TreeRoot object for the child.
        """
        if self._is_extension:
            raise ValidationError(f"Cannot prune an extension node: {self}")
        for child_id, child_root in child_pairs:
            if child_root._is_extension:
                if child_id != child_root._root_id:
                    raise ValidationError(
                        f"The child root must be itself if it's not the pruned node; "
                        f"child: {child_id}, pruning_node: {self}, child root: {child_root}"
                    )
                if child_root._extends_root is not self:
                    raise ValidationError(
                        f"The child extension root must be the pruned node {self}, "
                        f"not {child_root._extends_root}"
                    )
            elif child_root is not self:
                raise ValidationError(
                    f"Error while pruning node: child root {child_root} is not extension "
                    f"and is not the pruned node {self}"
                )
        prune_off_id = self.node_id
        old_depth_offset = self.depth_offset
        for child_id, child_root in child_pairs:
            child_root._prune(prune_off_id, child_id, old_depth_offset)

    @property
    def node_id(self) -> TNodeID:
        """
        Return the node all the way at the true root
        """
        true_root, _ = self._get_true_root()
        return true_root._root_id

    @property
    def depth_offset(self) -> int:
        """
        Return the depth all the way to the true root
        """
        true_root, extension = self._get_true_root()
        return true_root._depth_offset + extension

    def _get_true_root(self) -> Tuple['TreeRoot[TNodeID]', int]:
        """
        Return the true root (through all extensions), and the extended depth to it
        """
        candidate = self
        extended_depth = 0
        while candidate._is_extension:
            extended_depth += candidate._depth_extension
            candidate = candidate._extends_root
        return candidate, extended_depth

    def __repr__(self) -> str:
        if self._is_extension:
            return f"TreeRoot(<{self._extends_root!r}>, extended_by={self._depth_extension})"
        else:
            return f"TreeRoot({self._root_id}, offset={self._depth_offset})"


class RootTracker(Generic[TNodeID]):
    """
    This class tracks a graph that is presumed to be a single tree. The tree is built up one
    edge at a time, adding a new node, and the edge to its parent.

    The graph can be "built" in arbitrary order, so the graph may become a forest of trees
    at any moment. Additionally, nodes can be removed from the graph (pruned),
    but only at the root of one of the trees (aka the root of that tree).

    The primary thing tracked by this class is the root of each of the trees.
    This makes pruning each tree a much faster operation. Unfortunately, the worst case
    time to prune is still bad, O(n) of the depth of the tree. This worst case happens
    when all the nodes are added in reverse order. In the best case, the lookup is O(1).

    So it's important to understand how to optimize usage for the best case. Adding
    parents before children will give the best performance. Every inverted addition of
    a node will add a step to the root lookup time.
    """
    _roots: Dict[TNodeID, TreeRoot[TNodeID]]

    # "original" because root may have an offset for the final depth after pruning or adding parents
    _original_depth_to_root: Dict[TNodeID, int]

    _cache: Dict[TNodeID, Tuple[TNodeID, int]]

    def __init__(self) -> None:
        self._tree = Tree[TNodeID]()
        self._roots = {}
        self._original_depth_to_root = {}
        self._cache = {}

    def add(self, node_id: TNodeID, parent_id: TNodeID) -> None:
        """
        Add a node, and an edge to its parent, whether or not the parent is added yet
        """
        self._cache = {}
        self._tree.add(node_id, parent_id)

        node_root, original_depth = self._get_new_root(node_id, parent_id)
        self._roots[node_id] = node_root
        self._original_depth_to_root[node_id] = original_depth

        children = self._tree.children_of(node_id)
        self._link_children(node_root, original_depth, children)

    def get_children(self, node_id: TNodeID) -> Tuple[TNodeID, ...]:
        return self._tree.children_of(node_id)

    def get_root(self, node_id: TNodeID) -> Tuple[TNodeID, int]:
        """
        Look up the root of the tree that node_id is in, and the depth to that root.
        """
        if node_id not in self._roots:
            raise ValidationError(f"Node {node_id} is not in the tree")
        elif node_id in self._cache:
            (root_node_id, root_depth) = self._cache[node_id]
            if self._tree.has_parent(root_node_id):
                self._cache.pop(root_node_id)
                uncached_root = self.get_root(root_node_id)
                raise ValidationError(
                    f"RootTracker had stale and invalid cache for {node_id} root, "
                    f" correct: {root_node_id}, stale: {uncached_root}")
            else:
                return (root_node_id, root_depth)
        else:
            root = self._roots[node_id]
            original_depth = self._original_depth_to_root[node_id]
            (root_node_id, root_depth) = (root.node_id, original_depth + root.depth_offset)
            if self._tree.has_parent(root_node_id):
                parent = self._tree.parent_of(root_node_id)
                if parent in self._roots:
                    parent_root = self._roots[parent]
                else:
                    parent_root = None
                raise ValidationError(
                    f"{root_node_id} has parent {parent}, but was going to be returned as a root. "
                    f"{node_id} appears to have that bad root {root!r}, and the parent has bad "
                    f"root {parent_root!r}"
                )
            self._cache[node_id] = (root_node_id, root_depth)
            return self._cache[node_id]

    def prune(self, prune_off_id: TNodeID) -> None:
        """
        Prune off the node prune_off_id, which must be the root of its tree
        """
        if prune_off_id not in self._original_depth_to_root:
            raise ValidationError(f"prune id {prune_off_id} not in depths")
        elif prune_off_id not in self._roots:
            raise ValidationError(f"prune id {prune_off_id} not in roots")

        self._cache = {}
        root_to_prune = self._roots[prune_off_id]
        node_id = root_to_prune.node_id
        if node_id != prune_off_id:
            raise ValidationError(
                f"Can only prune of a root node, tried to prune {prune_off_id}, "
                f"but the root is {root_to_prune}"
            )
        elif self._tree.has_parent(node_id):
            parent = self._tree.parent_of(node_id)
            raise ValidationError(
                f"{node_id} has parent {parent}, but was about to be pruned"
            )

        child_nodes = self._tree.children_of(prune_off_id)
        child_pairs = tuple((child_node, self._roots[child_node]) for child_node in child_nodes)
        root_to_prune.prune_to(child_pairs)
        for child_node, child_root in child_pairs:
            if child_node != child_root.node_id:
                raise ValidationError(
                    f"Pruned child node should point to itself {child_node}, "
                    f"instead of {child_root.node_id}"
                )
        self._tree.prune(prune_off_id)
        self._original_depth_to_root.pop(prune_off_id)
        del self._roots[prune_off_id]

    def _get_new_root(self, node_id: TNodeID, parent_id: TNodeID) -> Tuple[TreeRoot[TNodeID], int]:
        if self._tree.has_parent(node_id):
            try:
                parent_root = self._roots[parent_id]
            except KeyError as e:
                tree_parent = self._tree.parent_of(node_id)
                raise ValidationError(
                    f"When adding node {node_id} with parent {parent_id}, The tree says that "
                    f"parent {tree_parent} is present, but the parent is missing from roots."
                ) from e

            if len(self._tree.children_of(parent_id)) > 1:
                node_root = TreeRoot(node_id)
                node_root.extend(parent_root, 0)
            else:
                node_root = parent_root
            original_depth = self._original_depth_to_root[parent_id] + 1
        else:
            node_root = TreeRoot(node_id)
            original_depth = 0

        return node_root, original_depth

    def _link_children(
            self,
            parent_root: TreeRoot[TNodeID],
            parent_original_depth: int,
            children: Tuple[TNodeID, ...]) -> None:

        for child in children:
            child_root = self._roots[child]

            if child_root.depth_offset + self._original_depth_to_root[child] != 0:
                raise ValidationError(
                    "children without parents must have net depth 0: "
                    f"but offset was {child_root.depth_offset} and original depth "
                    f"was {self._original_depth_to_root[child]}."
                )
            else:
                # original depth was 0, needs to be adjusted based on parent's original depth
                ideal_original_depth = parent_original_depth + 1
                actual_original_depth = self._original_depth_to_root[child]
                # extension length = ideal - actual = ideal - 0
                child_root.extend(parent_root, ideal_original_depth - actual_original_depth)
