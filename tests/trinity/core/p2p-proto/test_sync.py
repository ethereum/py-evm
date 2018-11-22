import asyncio

import pytest

from eth_keys import keys
from eth_utils import decode_hex

from eth import constants
from eth.tools.mining import POWMiningMixin
from eth.vm.forks.frontier import FrontierVM

from trinity.plugins.builtin.block_importer import (
    BlockImportHandler,
    EventBusBlockImporter,
)
from trinity.protocol.eth.servers import ETHRequestServer
from trinity.protocol.les.peer import LESPeer
from trinity.protocol.les.servers import LightRequestServer
from trinity.sync.full.chain import FastChainSyncer, RegularChainSyncer
from trinity.sync.full.state import StateDownloader
from trinity.sync.light.chain import LightChainSyncer

from tests.trinity.core.integration_test_helpers import (
    FakeAsyncChain,
    FakeAsyncChainDB,
    FakeAsyncHeaderDB,
    FakeAsyncAtomicDB,
)
from tests.trinity.core.peer_helpers import (
    get_directly_linked_peers,
    MockPeerPoolWithConnectedPeers,
)


# This causes the chain syncers to request/send small batches of things, which will cause us to
# exercise parts of the code that wouldn't otherwise be exercised if the whole sync was completed
# by requesting a single batch.
@pytest.fixture(autouse=True)
def small_header_batches(monkeypatch):
    from trinity.protocol.eth import constants
    monkeypatch.setattr(constants, 'MAX_HEADERS_FETCH', 10)
    monkeypatch.setattr(constants, 'MAX_BODIES_FETCH', 5)


@pytest.mark.asyncio
async def test_fast_syncer(request, event_loop, chaindb_fresh, chaindb_20):
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        alice_headerdb=FakeAsyncHeaderDB(chaindb_fresh.db),
        bob_headerdb=FakeAsyncHeaderDB(chaindb_20.db))
    client_peer_pool = MockPeerPoolWithConnectedPeers([client_peer])
    client = FastChainSyncer(FrontierTestChain(chaindb_fresh.db), chaindb_fresh, client_peer_pool)
    server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer])
    server = RegularChainSyncer(
        FrontierTestChain(chaindb_20.db),
        chaindb_20,
        server_peer_pool,
    )
    asyncio.ensure_future(server.run())
    server_request_handler = ETHRequestServer(FakeAsyncChainDB(chaindb_20.db), server_peer_pool)
    asyncio.ensure_future(server_request_handler.run())
    server_peer.logger.info("%s is serving 20 blocks", server_peer)
    client_peer.logger.info("%s is syncing up 20", client_peer)

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
    state_downloader = StateDownloader(
        chaindb_fresh, chaindb_fresh.db, head.state_root, client_peer_pool)
    await asyncio.wait_for(state_downloader.run(), timeout=2)

    assert head.state_root in chaindb_fresh.db


@pytest.mark.asyncio
async def test_regular_syncer(request, event_loop, event_bus, chaindb_fresh, chaindb_20):

    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        alice_headerdb=FakeAsyncHeaderDB(chaindb_fresh.db),
        bob_headerdb=FakeAsyncHeaderDB(chaindb_20.db))

    client_chain = FrontierTestChain(chaindb_fresh.db)
    client_block_import_handler = BlockImportHandler(client_chain, event_bus)
    client_block_import_api = EventBusBlockImporter(event_bus)

    client = RegularChainSyncer(
        client_chain,
        chaindb_fresh,
        MockPeerPoolWithConnectedPeers([client_peer]),
        block_import_fn=client_block_import_api.coro_import_block)
    server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer])

    server_chain = FrontierTestChain(chaindb_20.db)
    server_block_import_handler = BlockImportHandler(server_chain, event_bus)
    server_block_import_api = EventBusBlockImporter(event_bus)

    server = RegularChainSyncer(
        server_chain,
        chaindb_20,
        server_peer_pool,
        block_import_fn=server_block_import_api.coro_import_block
    )
    asyncio.ensure_future(server.run())
    server_request_handler = ETHRequestServer(FakeAsyncChainDB(chaindb_20.db), server_peer_pool)
    asyncio.ensure_future(server_request_handler.run())
    server_peer.logger.info("%s is serving 20 blocks", server_peer)
    client_peer.logger.info("%s is syncing up 20", client_peer)

    def finalizer():
        event_loop.run_until_complete(asyncio.gather(
            client.cancel(),
            server.cancel(),
            client_block_import_handler.cancel(),
            server_block_import_handler.cancel(),
            loop=event_loop,
        ))
        # Yield control so that client/server.run() returns, otherwise asyncio will complain.
        event_loop.run_until_complete(asyncio.sleep(0.1))
    request.addfinalizer(finalizer)

    asyncio.ensure_future(client.run())
    asyncio.ensure_future(client_block_import_handler.run())
    asyncio.ensure_future(server_block_import_handler.run())

    await wait_for_head(client.db, server.db.get_canonical_head())
    head = client.db.get_canonical_head()
    assert head.state_root in client.db.db


@pytest.mark.asyncio
async def test_light_syncer(request, event_loop, chaindb_fresh, chaindb_20):
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        alice_peer_class=LESPeer,
        alice_headerdb=FakeAsyncHeaderDB(chaindb_fresh.db),
        bob_headerdb=FakeAsyncHeaderDB(chaindb_20.db))
    client = LightChainSyncer(
        FrontierTestChain(chaindb_fresh.db),
        chaindb_fresh,
        MockPeerPoolWithConnectedPeers([client_peer]))
    server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer])
    server = LightChainSyncer(
        FrontierTestChain(chaindb_20.db),
        chaindb_20,
        server_peer_pool,
    )
    asyncio.ensure_future(server.run())
    server_request_handler = LightRequestServer(FakeAsyncHeaderDB(chaindb_20.db), server_peer_pool)
    asyncio.ensure_future(server_request_handler.run())
    server_peer.logger.info("%s is serving 20 blocks", server_peer)
    client_peer.logger.info("%s is syncing up 20", client_peer)

    def finalizer():
        event_loop.run_until_complete(asyncio.gather(
            client.cancel(),
            server.cancel(),
            loop=event_loop,
        ))
        # Yield control so that client/server.run() returns, otherwise asyncio will complain.
        event_loop.run_until_complete(asyncio.sleep(0.1))
    request.addfinalizer(finalizer)

    asyncio.ensure_future(client.run())

    await wait_for_head(client.db, server.db.get_canonical_head())


@pytest.fixture
def chaindb_20():
    chain = PoWMiningChain.from_genesis(FakeAsyncAtomicDB(), GENESIS_PARAMS, GENESIS_STATE)
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
    chain = PoWMiningChain.from_genesis(FakeAsyncAtomicDB(), GENESIS_PARAMS, GENESIS_STATE)
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
    'gas_limit': 3141592,
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


class POWFrontierVM(POWMiningMixin, FrontierVM):
    pass


class PoWMiningChain(FrontierTestChain):
    vm_configuration = ((0, POWFrontierVM),)


async def wait_for_head(headerdb, header):
    # A full header sync may involve several round trips, so we must be willing to wait a little
    # bit for them.
    HEADER_SYNC_TIMEOUT = 3

    async def wait_loop():
        while headerdb.get_canonical_head() != header:
            await asyncio.sleep(0.1)
    await asyncio.wait_for(wait_loop(), HEADER_SYNC_TIMEOUT)
