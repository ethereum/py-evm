import asyncio
import socket

import pytest

from p2p.tools.factories import (
    AddressFactory,
    DiscoveryProtocolFactory,
    NodeFactory,
)


"""
NOTE: These tests end up making actual network connections
"""


async def get_listening_discovery_protocol(event_loop):
    addr = AddressFactory.localhost()
    proto = DiscoveryProtocolFactory(address=addr)
    await event_loop.create_datagram_endpoint(
        lambda: proto, local_addr=(addr.ip, addr.udp_port), family=socket.AF_INET)
    return proto


@pytest.mark.asyncio
async def test_topic_query(event_loop):
    bob = await get_listening_discovery_protocol(event_loop)
    les_nodes = NodeFactory.create_batch(10)
    topic = b'les'
    for n in les_nodes:
        bob.topic_table.add_node(n, topic)
    alice = await get_listening_discovery_protocol(event_loop)

    echo = alice.send_topic_query(bob.this_node, topic)
    received_nodes = await alice.wait_topic_nodes(bob.this_node, echo)

    assert len(received_nodes) == 10
    assert sorted(received_nodes) == sorted(les_nodes)


@pytest.mark.asyncio
async def test_topic_register(event_loop):
    bob = await get_listening_discovery_protocol(event_loop)
    alice = await get_listening_discovery_protocol(event_loop)
    topics = [b'les', b'les2']

    # In order to register ourselves under a given topic we need to first get a ticket.
    ticket = await bob.get_ticket(alice.this_node, topics)

    assert ticket is not None
    assert ticket.topics == topics
    assert ticket.node == alice.this_node
    assert len(ticket.registration_times) == 2

    # Now we register ourselves under one of the topics for which we have a ticket.
    topic_idx = 0
    bob.send_topic_register(alice.this_node, ticket.topics, topic_idx, ticket.pong)
    await asyncio.sleep(0.2)

    topic_nodes = alice.topic_table.get_nodes(topics[topic_idx])
    assert len(topic_nodes) == 1
    assert topic_nodes[0] == bob.this_node
