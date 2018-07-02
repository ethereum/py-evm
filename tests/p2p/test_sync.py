import asyncio

import pytest

from eth_keys import keys
from eth_utils import decode_hex

from evm import constants
from evm.db.backends.memory import MemoryDB
from evm.vm.forks.frontier import FrontierVM, _PoWMiningVM

from p2p import eth
from p2p.peer import ETHPeer, LESPeer
from p2p.chain import FastChainSyncer, LightChainSyncer, RegularChainSyncer
from p2p.state import StateDownloader

from integration_test_helpers import FakeAsyncChain, FakeAsyncChainDB, FakeAsyncHeaderDB
from peer_helpers import get_directly_linked_peers, MockPeerPoolWithConnectedPeers


# This causes the chain syncers to request/send small batches of things, which will cause us to
# exercise parts of the code that wouldn't otherwise be exercised if the whole sync was completed
# by requesting a single batch.
@pytest.fixture(autouse=True)
def small_header_batches(monkeypatch):
    monkeypatch.setattr(eth, 'MAX_HEADERS_FETCH', 10)
    monkeypatch.setattr(eth, 'MAX_BODIES_FETCH', 5)


@pytest.mark.asyncio
async def test_fast_syncer(request, event_loop, chaindb_fresh, chaindb_20):
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        ETHPeer, FakeAsyncHeaderDB(chaindb_fresh.db),
        ETHPeer, FakeAsyncHeaderDB(chaindb_20.db))
    client_peer_pool = MockPeerPoolWithConnectedPeers([client_peer])
    client = FastChainSyncer(FrontierTestChain(chaindb_fresh.db), chaindb_fresh, client_peer_pool)
    server = RegularChainSyncer(
        FrontierTestChain(chaindb_20.db),
        chaindb_20,
        MockPeerPoolWithConnectedPeers([server_peer]))
    asyncio.ensure_future(server.run())

    def finalizer():
        event_loop.run_until_complete(server.cancel())
        # Yield control so that server.run() returns, otherwise asyncio will complain.
        event_loop.run_until_complete(asyncio.sleep(0.1))
    request.addfinalizer(finalizer)

    # FastChainSyncer.run() will return as soon as it's caught up with the peer.
    await asyncio.wait_for(client.run(), timeout=2)

    head = chaindb_fresh.get_canonical_head()
    assert head == chaindb_20.get_canonical_head()

    # Now download the state for the chain's head.
    state_downloader = StateDownloader(chaindb_fresh.db, head.state_root, client_peer_pool)
    await asyncio.wait_for(state_downloader.run(), timeout=2)

    assert head.state_root in chaindb_fresh.db


@pytest.mark.asyncio
async def test_regular_syncer(request, event_loop, chaindb_fresh, chaindb_20):
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        ETHPeer, FakeAsyncHeaderDB(chaindb_fresh.db),
        ETHPeer, FakeAsyncHeaderDB(chaindb_20.db))
    client = RegularChainSyncer(
        FrontierTestChain(chaindb_fresh.db),
        chaindb_fresh,
        MockPeerPoolWithConnectedPeers([client_peer]))
    server = RegularChainSyncer(
        FrontierTestChain(chaindb_20.db),
        chaindb_20,
        MockPeerPoolWithConnectedPeers([server_peer]))
    asyncio.ensure_future(server.run())

    def finalizer():
        event_loop.run_until_complete(asyncio.gather(client.cancel(), server.cancel()))
        # Yield control so that client/server.run() returns, otherwise asyncio will complain.
        event_loop.run_until_complete(asyncio.sleep(0.1))
    request.addfinalizer(finalizer)

    asyncio.ensure_future(client.run())

    await wait_for_head(client.db, server.db.get_canonical_head())
    head = client.db.get_canonical_head()
    assert head.state_root in client.db.db


@pytest.mark.asyncio
async def test_light_syncer(request, event_loop, chaindb_fresh, chaindb_20):
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        LESPeer, FakeAsyncHeaderDB(chaindb_fresh.db),
        LESPeer, FakeAsyncHeaderDB(chaindb_20.db))
    client = LightChainSyncer(
        FrontierTestChain(chaindb_fresh.db),
        chaindb_fresh,
        MockPeerPoolWithConnectedPeers([client_peer]))
    server = LightChainSyncer(
        FrontierTestChain(chaindb_20.db),
        chaindb_20,
        MockPeerPoolWithConnectedPeers([server_peer]))
    asyncio.ensure_future(server.run())

    def finalizer():
        event_loop.run_until_complete(asyncio.gather(client.cancel(), server.cancel()))
        # Yield control so that client/server.run() returns, otherwise asyncio will complain.
        event_loop.run_until_complete(asyncio.sleep(0.1))
    request.addfinalizer(finalizer)

    asyncio.ensure_future(client.run())

    await wait_for_head(client.db, server.db.get_canonical_head())


@pytest.fixture
def chaindb_20():
    chain = PoWMiningChain.from_genesis(MemoryDB(), GENESIS_PARAMS, GENESIS_STATE)
    for i in range(20):
        tx = chain.create_unsigned_transaction(
            nonce=i,
            gas_price=1234,
            gas=1234000,
            to=RECEIVER.public_key.to_canonical_address(),
            value=i,
            data=b'',
        )
        chain.apply_transaction(tx.as_signed_transaction(SENDER))
        chain.mine_block()
    return chain.chaindb


@pytest.fixture
def chaindb_fresh():
    chain = PoWMiningChain.from_genesis(MemoryDB(), GENESIS_PARAMS, GENESIS_STATE)
    assert chain.chaindb.get_canonical_head().block_number == 0
    return chain.chaindb


SENDER = keys.PrivateKey(
    decode_hex("49a7b37aa6f6645917e7b807e9d1c00d4fa71f18343b0d4122a4d2df64dd6fee"))
RECEIVER = keys.PrivateKey(
    decode_hex("b71c71a67e1177ad4e901695e1b4b9ee17ae16c6668d313eac2f96dbcda3f291"))
GENESIS_PARAMS = {
    'parent_hash': constants.GENESIS_PARENT_HASH,
    'uncles_hash': constants.EMPTY_UNCLE_HASH,
    'coinbase': constants.ZERO_ADDRESS,
    'transaction_root': constants.BLANK_ROOT_HASH,
    'receipt_root': constants.BLANK_ROOT_HASH,
    'bloom': 0,
    'difficulty': 5,
    'block_number': constants.GENESIS_BLOCK_NUMBER,
    'gas_limit': constants.GENESIS_GAS_LIMIT,
    'gas_used': 0,
    'timestamp': 1514764800,
    'extra_data': constants.GENESIS_EXTRA_DATA,
    'nonce': constants.GENESIS_NONCE
}
GENESIS_STATE = {
    SENDER.public_key.to_canonical_address(): {
        "balance": 100000000000000000,
        "code": b"",
        "nonce": 0,
        "storage": {}
    }
}


class FrontierTestChain(FakeAsyncChain):
    vm_configuration = ((0, FrontierVM),)
    chaindb_class = FakeAsyncChainDB
    network_id = 999


class PoWMiningChain(FrontierTestChain):
    vm_configuration = ((0, _PoWMiningVM),)


async def wait_for_head(headerdb, header):
    # A full header sync may involve several round trips, so we must be willing to wait a little
    # bit for them.
    HEADER_SYNC_TIMEOUT = 3

    async def wait_loop():
        while headerdb.get_canonical_head() != header:
            await asyncio.sleep(0.1)
    await asyncio.wait_for(wait_loop(), HEADER_SYNC_TIMEOUT)
