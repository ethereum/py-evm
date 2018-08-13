import os
import random

import pytest

from eth_utils import keccak

from p2p.exceptions import ValidationError

from trinity.protocol.eth.requests import NodeDataRequest


def mk_node():
    node_length = random.randint(0, 2048)
    node = os.urandom(node_length)
    return node


def mk_node_data(n):
    if n == 0:
        return tuple(), tuple()
    nodes = tuple(set(mk_node() for _ in range(n)))
    node_keys = tuple(keccak(node) for node in nodes)
    return node_keys, nodes


def test_node_data_request_empty_response_is_valid():
    node_keys, _ = mk_node_data(10)
    request = NodeDataRequest(node_keys)

    request.validate_response(tuple(), tuple())


def test_node_data_request_with_full_response():
    node_keys, nodes = mk_node_data(10)
    request = NodeDataRequest(node_keys)
    node_data = tuple(zip(node_keys, nodes))

    request.validate_response(nodes, node_data)


def test_node_data_request_with_partial_response():
    node_keys, nodes = mk_node_data(10)
    request = NodeDataRequest(node_keys)
    node_data = tuple(zip(node_keys, nodes))

    request.validate_response(nodes[3:], node_data[3:])
    request.validate_response(nodes[:3], node_data[:3])
    request.validate_response(
        (nodes[1], nodes[8], nodes[4]),
        (node_data[1], node_data[8], node_data[4]),
    )


def test_node_data_request_with_fully_invalid_response():
    node_keys, nodes = mk_node_data(10)
    request = NodeDataRequest(node_keys)

    # construct a unique set of other nodes
    other_nodes = tuple(set(mk_node() for _ in range(10)).difference(nodes))
    other_node_data = tuple((keccak(node), node) for node in other_nodes)

    with pytest.raises(ValidationError):
        request.validate_response(other_nodes, other_node_data)


def test_node_data_request_with_extra_unrequested_nodes():
    node_keys, nodes = mk_node_data(10)
    request = NodeDataRequest(node_keys)
    node_data = tuple(zip(node_keys, nodes))

    # construct a unique set of other nodes
    other_nodes = tuple(set(mk_node() for _ in range(10)).difference(nodes))
    other_node_data = tuple((keccak(node), node) for node in other_nodes)

    with pytest.raises(ValidationError):
        request.validate_response(
            nodes + other_nodes,
            node_data + other_node_data,
        )
