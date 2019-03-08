import pytest

from eth_utils import ValidationError
from hypothesis import (
    given,
    settings,
    strategies as st,
)

from trinity._utils.tree_root import Tree, RootTracker


@given(st.permutations(range(10)))
def test_tree_linking(add_order):
    # node and parent id
    nodes = (
        ('A0', '_'),
        ('A1', '_'),
        ('B0', 'A0'),
        ('C0', 'B0'),
        ('C1', 'B0'),
        ('C2', 'B0'),
        ('D0', 'C0'),
        ('D1', 'C0'),
        ('D2', 'C0'),
        ('E0', 'D0'),
    )

    tree = Tree()
    for node_idx in add_order:
        node, parent = nodes[node_idx]
        tree.add(node, parent)

    assert not tree.has_parent('A0')
    assert not tree.has_parent('A1')
    assert not tree.has_node('_')
    assert tree.has_node('A0')
    assert tree.has_node('A1')
    assert tree.children_of('A0') == ('B0',)
    assert tree.children_of('A1') == tuple()

    for node, parent in nodes[2:]:
        assert tree.has_node(node)

        assert tree.has_parent(node)
        assert tree.parent_of(node) == parent

        children = tree.children_of(parent)
        assert node in children

        if parent in ('B0', 'C0'):
            assert len(children) == 3
        elif parent in ('A0', 'D0'):
            assert len(children) == 1
        else:
            assert len(children) == 0


@given(st.permutations(range(10)))
def test_out_of_order_line(insertion_order):
    tracker = RootTracker()
    for node in insertion_order:
        tracker.add(node, node - 1)

    for expected_root in range(9):
        for node in range(expected_root, 10):
            root, depth = tracker.get_root(node)
            assert depth == node - expected_root
            assert root == expected_root

        # always prune from the end
        prune_root_id, _ = tracker.get_root(9)
        tracker.prune(prune_root_id)

        # root should not be retrievable anymore
        with pytest.raises(ValidationError):
            tracker.get_root(prune_root_id)


@given(st.lists(st.integers(min_value=0, max_value=9)))
def test_prune_reinsert_root_tracking_linear(element_flipping):
    tracker = RootTracker()

    present = set()
    for node in element_flipping:
        if node in present:
            prune_root_id, _ = tracker.get_root(node)
            tracker.prune(prune_root_id)
            present.remove(prune_root_id)
        else:
            tracker.add(node, node - 1)
            present.add(node)

        # validate all the present nodes have valid roots
        for test_node in present:
            root_id, depth = tracker.get_root(test_node)

            # make sure parent is *not* present
            assert root_id - 1 not in present

            # make sure depth is correct
            assert depth == test_node - root_id


FULL_BINARY_TREE = [(layer, column) for layer in [0, 1, 2, 3] for column in range(2**layer)]


def binary_parent(node):
    return (node[0] - 1, node[1] // 2)


# only use the first 3 layers of the tree
@given(st.lists(
    st.integers(min_value=0, max_value=6),
    min_size=3,
))
def test_prune_reinsert_root_tracking_binary_tree(element_flipping):
    tracker = RootTracker()

    present = set()
    for node_id in element_flipping:
        node = FULL_BINARY_TREE[node_id]
        if node in present:
            prune_root_id, _ = tracker.get_root(node)
            tracker.prune(prune_root_id)
            present.remove(prune_root_id)
        else:
            tracker.add(node, binary_parent(node))
            present.add(node)

        # validate all the present nodes have valid roots
        for test_node in present:
            root_node, depth = tracker.get_root(test_node)

            # make sure parent is *not* present
            assert binary_parent(root_node) not in present

            # make sure depth is correct
            assert depth == test_node[0] - root_node[0]


@given(st.permutations(FULL_BINARY_TREE))
def test_full_branching(insertion_order):
    """Test full binary tree, in random order"""
    tracker = RootTracker()
    for node in insertion_order:
        tracker.add(node, binary_parent(node))

    # prune all the way to the leaf of (3, 0)
    for num_prunings in range(3):
        root_id, depth = tracker.get_root((3, 0))
        assert root_id[0] == num_prunings
        assert depth == 3 - num_prunings
        tracker.prune(root_id)
        assert tracker.get_root((3, 7)) == ((1, 1), 2)


@st.composite
def subset_and_order(draw):
    nodes_to_insert = draw(st.lists(st.sampled_from(FULL_BINARY_TREE), unique=True))
    prune_order = draw(st.permutations(range(len(nodes_to_insert))))
    return (nodes_to_insert, prune_order)


@given(subset_and_order())
@settings(max_examples=500)
def test_sparse_branching(test_data):
    nodes_to_insert, prune_order = test_data

    def get_expected_root(node, present_nodes):
        expected_depth = 0
        expected_root = node
        parent_node = binary_parent(node)
        while parent_node in present_nodes:
            expected_depth += 1
            expected_root = parent_node
            parent_node = binary_parent(parent_node)
        return expected_root, expected_depth

    tracker = RootTracker()
    for node in nodes_to_insert:
        tracker.add(node, binary_parent(node))

    # verify parent and depth of partially-built tree
    for node in nodes_to_insert:
        actual_root, actual_depth = tracker.get_root(node)
        expected_root, expected_depth = get_expected_root(node, nodes_to_insert)
        assert actual_root == expected_root
        assert actual_depth == expected_depth

    # prune
    remaining_nodes = set(nodes_to_insert)
    for prune_idx in [idx for idx in prune_order if idx < len(nodes_to_insert)]:
        node_to_prune_from = nodes_to_insert[prune_idx]
        if node_to_prune_from not in remaining_nodes:
            continue
        prune_root_id, _ = tracker.get_root(node_to_prune_from)
        tracker.prune(prune_root_id)
        remaining_nodes.remove(prune_root_id)

        for node in remaining_nodes:
            actual_root, actual_depth = tracker.get_root(node)
            expected_root, expected_depth = get_expected_root(node, remaining_nodes)
            assert actual_root == expected_root
            assert actual_depth == expected_depth
