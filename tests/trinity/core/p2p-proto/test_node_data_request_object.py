import os
import random

import pytest

from eth_utils import (
    keccak,
    ValidationError,
)

from trinity.protocol.eth.validators import GetNodeDataValidator


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
    validator = GetNodeDataValidator(node_keys)

    validator.validate_result(tuple())


def test_node_data_request_with_full_response():
    node_keys, nodes = mk_node_data(10)
    validator = GetNodeDataValidator(node_keys)
    node_data = tuple(zip(node_keys, nodes))

    validator.validate_result(node_data)


def test_node_data_request_with_partial_response():
    node_keys, nodes = mk_node_data(10)
    validator = GetNodeDataValidator(node_keys)
    node_data = tuple(zip(node_keys, nodes))

    validator.validate_result(node_data[3:])

    validator.validate_result(node_data[:3])

    validator.validate_result((node_data[1], node_data[8], node_data[4]))


def test_node_data_request_with_fully_invalid_response():
    node_keys, nodes = mk_node_data(10)
    validator = GetNodeDataValidator(node_keys)

    # construct a unique set of other nodes
    other_nodes = tuple(set(mk_node() for _ in range(10)).difference(nodes))
    other_node_data = tuple((keccak(node), node) for node in other_nodes)

    with pytest.raises(ValidationError):
        validator.validate_result(other_node_data)


def test_node_data_request_with_extra_unrequested_nodes():
    node_keys, nodes = mk_node_data(10)
    validator = GetNodeDataValidator(node_keys)
    node_data = tuple(zip(node_keys, nodes))

    # construct a unique set of other nodes
    other_nodes = tuple(set(mk_node() for _ in range(10)).difference(nodes))
    other_node_data = tuple((keccak(node), node) for node in other_nodes)

    with pytest.raises(ValidationError):
        validator.validate_result(node_data + other_node_data)
