import asyncio
import os
import random
import time

import pytest

import rlp

from eth_utils import (
    big_endian_to_int,
    keccak,
    to_tuple,
)

from eth.db.trie import make_trie_root_and_nodes
from eth.rlp.headers import BlockHeader
from eth.rlp.transactions import BaseTransactionFields

from trinity.rlp.block_body import BlockBody

from trinity.tools.factories import ETHPeerPairFactory


def mk_uncle(block_number):
    return BlockHeader(
        state_root=os.urandom(32),
        difficulty=1000000,
        block_number=block_number,
        gas_limit=3141592,
        timestamp=int(time.time()),
    )


def mk_transaction():
    return BaseTransactionFields(
        nonce=0,
        gas=21000,
        gas_price=1,
        to=os.urandom(20),
        value=random.randint(0, 100),
        data=b'',
        v=27,
        r=big_endian_to_int(os.urandom(32)),
        s=big_endian_to_int(os.urandom(32)),
    )


def mk_header_and_body(block_number, num_transactions, num_uncles):
    transactions = tuple(mk_transaction() for _ in range(num_transactions))
    uncles = tuple(mk_uncle(block_number - 1) for _ in range(num_uncles))

    transaction_root, trie_data = make_trie_root_and_nodes(transactions)
    uncles_hash = keccak(rlp.encode(uncles))

    body = BlockBody(transactions=transactions, uncles=uncles)

    header = BlockHeader(
        difficulty=1000000,
        block_number=block_number,
        gas_limit=3141592,
        timestamp=int(time.time()),
        transaction_root=transaction_root,
        uncles_hash=uncles_hash,
    )

    return header, body, transaction_root, trie_data, uncles_hash


@to_tuple
def mk_headers(*counts):
    for idx, (num_transactions, num_uncles) in enumerate(counts, 1):
        yield mk_header_and_body(idx, num_transactions, num_uncles)


@pytest.fixture
async def eth_peer_and_remote():
    async with ETHPeerPairFactory() as (peer, remote):
        yield peer, remote


@pytest.mark.asyncio
async def test_eth_peer_get_block_bodies_round_trip_with_empty_response(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, bodies, transactions_roots, trie_data_dicts, uncles_hashes = zip(*headers_bundle)

    async def send_block_bodies():
        remote.sub_proto.send_block_bodies([])
        await asyncio.sleep(0)

    get_bodies_task = asyncio.ensure_future(peer.requests.get_block_bodies(headers))
    asyncio.ensure_future(send_block_bodies())

    response = await get_bodies_task

    assert len(response) == 0


@pytest.mark.asyncio
async def test_eth_peer_get_block_bodies_round_trip_with_full_response(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, bodies, transactions_roots, trie_data_dicts, uncles_hashes = zip(*headers_bundle)

    async def send_block_bodies():
        remote.sub_proto.send_block_bodies(bodies)
        await asyncio.sleep(0)

    transactions_bundles = tuple(zip(transactions_roots, trie_data_dicts))
    bodies_bundle = tuple(zip(bodies, transactions_bundles, uncles_hashes))

    get_bodies_task = asyncio.ensure_future(peer.requests.get_block_bodies(headers))
    asyncio.ensure_future(send_block_bodies())

    response = await get_bodies_task

    assert len(response) == 4
    assert response == bodies_bundle


@pytest.mark.asyncio
async def test_eth_peer_get_block_bodies_round_trip_with_partial_response(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, bodies, transactions_roots, trie_data_dicts, uncles_hashes = zip(*headers_bundle)

    async def send_block_bodies():
        remote.sub_proto.send_block_bodies(bodies[1:])
        await asyncio.sleep(0)

    transactions_bundles = tuple(zip(transactions_roots, trie_data_dicts))
    bodies_bundle = tuple(zip(bodies, transactions_bundles, uncles_hashes))

    get_bodies_task = asyncio.ensure_future(peer.requests.get_block_bodies(headers))
    asyncio.ensure_future(send_block_bodies())

    response = await get_bodies_task

    assert len(response) == 3
    assert response == bodies_bundle[1:]


@pytest.mark.asyncio
async def test_eth_peer_get_block_bodies_round_trip_with_noise(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, bodies, transactions_roots, trie_data_dicts, uncles_hashes = zip(*headers_bundle)

    async def send_block_bodies():
        remote.sub_proto.send_node_data((b'', b'arst'))
        await asyncio.sleep(0)
        remote.sub_proto.send_block_bodies(bodies)
        await asyncio.sleep(0)
        remote.sub_proto.send_node_data((b'', b'arst'))
        await asyncio.sleep(0)

    transactions_bundles = tuple(zip(transactions_roots, trie_data_dicts))
    bodies_bundle = tuple(zip(bodies, transactions_bundles, uncles_hashes))

    get_bodies_task = asyncio.ensure_future(peer.requests.get_block_bodies(headers))
    asyncio.ensure_future(send_block_bodies())

    response = await get_bodies_task

    assert len(response) == 4
    assert response == bodies_bundle


@pytest.mark.asyncio
async def test_eth_peer_get_block_bodies_round_trip_no_match_invalid_response(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    headers_bundle = mk_headers((2, 3), (8, 4), (0, 1), (0, 0))
    headers, bodies, transactions_roots, trie_data_dicts, uncles_hashes = zip(*headers_bundle)

    wrong_headers_bundle = mk_headers((4, 1), (3, 5), (2, 0), (7, 3))
    _, wrong_bodies, _, _, _ = zip(*wrong_headers_bundle)

    async def send_block_bodies():
        remote.sub_proto.send_block_bodies(wrong_bodies)
        await asyncio.sleep(0)
        remote.sub_proto.send_block_bodies(bodies)
        await asyncio.sleep(0)

    transactions_bundles = tuple(zip(transactions_roots, trie_data_dicts))
    bodies_bundle = tuple(zip(bodies, transactions_bundles, uncles_hashes))

    get_bodies_task = asyncio.ensure_future(peer.requests.get_block_bodies(headers))
    asyncio.ensure_future(send_block_bodies())

    response = await get_bodies_task

    assert len(response) == 4
    assert response == bodies_bundle
