import asyncio

import pytest

from p2p.service import BaseService

from trinity.protocol.eth.peer import ETHPeerPoolEventServer
from trinity.protocol.eth.sync import ETHHeaderChainSyncer
from trinity.protocol.les.peer import LESPeer
from trinity.protocol.les.servers import LightRequestServer
from trinity.sync.common.chain import (
    SimpleBlockImporter,
)
from trinity.sync.full.chain import FastChainSyncer, RegularChainSyncer, RegularChainBodySyncer

from trinity.protocol.les.peer import (
    LESPeerPoolEventServer,
)

from trinity.sync.full.state import StateDownloader
from trinity.sync.light.chain import LightChainSyncer

from tests.core.integration_test_helpers import (
    ByzantiumTestChain,
    DBFixture,
    FakeAsyncAtomicDB,
    FakeAsyncChainDB,
    FakeAsyncHeaderDB,
    load_fixture_db,
    load_mining_chain,
    run_peer_pool_event_server,
    run_request_server,
)
from tests.core.peer_helpers import (
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
async def test_fast_syncer(request,
                           event_bus,
                           event_loop,
                           chaindb_fresh,
                           chaindb_20):
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        alice_headerdb=FakeAsyncHeaderDB(chaindb_fresh.db),
        bob_headerdb=FakeAsyncHeaderDB(chaindb_20.db))
    client_peer_pool = MockPeerPoolWithConnectedPeers([client_peer])
    client = FastChainSyncer(ByzantiumTestChain(chaindb_fresh.db), chaindb_fresh, client_peer_pool)
    server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

    async with run_peer_pool_event_server(
        event_bus,
        server_peer_pool,
        handler_type=ETHPeerPoolEventServer,
    ), run_request_server(
        event_bus,
        FakeAsyncChainDB(chaindb_20.db),
    ):

        server_peer.logger.info("%s is serving 20 blocks", server_peer)
        client_peer.logger.info("%s is syncing up 20", client_peer)

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
async def test_skeleton_syncer(request, event_loop, event_bus, chaindb_fresh, chaindb_1000):
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        alice_headerdb=FakeAsyncHeaderDB(chaindb_fresh.db),
        bob_headerdb=FakeAsyncHeaderDB(chaindb_1000.db))
    client_peer_pool = MockPeerPoolWithConnectedPeers([client_peer])
    client = FastChainSyncer(ByzantiumTestChain(chaindb_fresh.db), chaindb_fresh, client_peer_pool)
    server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

    async with run_peer_pool_event_server(
        event_bus, server_peer_pool, handler_type=ETHPeerPoolEventServer
    ), run_request_server(
        event_bus, FakeAsyncChainDB(chaindb_1000.db)
    ):

        client_peer.logger.info("%s is serving 1000 blocks", client_peer)
        server_peer.logger.info("%s is syncing up 1000 blocks", server_peer)

        await asyncio.wait_for(client.run(), timeout=20)

        head = chaindb_fresh.get_canonical_head()
        assert head == chaindb_1000.get_canonical_head()

        # Now download the state for the chain's head.
        state_downloader = StateDownloader(
            chaindb_fresh, chaindb_fresh.db, head.state_root, client_peer_pool)
        await asyncio.wait_for(state_downloader.run(), timeout=20)

        assert head.state_root in chaindb_fresh.db


@pytest.mark.asyncio
async def test_regular_syncer(request, event_loop, event_bus, chaindb_fresh, chaindb_20):
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        alice_headerdb=FakeAsyncHeaderDB(chaindb_fresh.db),
        bob_headerdb=FakeAsyncHeaderDB(chaindb_20.db))
    client = RegularChainSyncer(
        ByzantiumTestChain(chaindb_fresh.db),
        chaindb_fresh,
        MockPeerPoolWithConnectedPeers([client_peer]))
    server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

    async with run_peer_pool_event_server(
        event_bus, server_peer_pool, handler_type=ETHPeerPoolEventServer
    ), run_request_server(
        event_bus, FakeAsyncChainDB(chaindb_20.db)
    ):

        server_peer.logger.info("%s is serving 20 blocks", server_peer)
        client_peer.logger.info("%s is syncing up 20", client_peer)

        def finalizer():
            event_loop.run_until_complete(client.cancel())
            # Yield control so that client/server.run() returns, otherwise asyncio will complain.
            event_loop.run_until_complete(asyncio.sleep(0.1))
        request.addfinalizer(finalizer)

        asyncio.ensure_future(client.run())

        await wait_for_head(chaindb_fresh, chaindb_20.get_canonical_head())
        head = chaindb_fresh.get_canonical_head()
        assert head.state_root in chaindb_fresh.db


class FallbackTesting_RegularChainSyncer(BaseService):
    class HeaderSyncer_OnlyOne:
        def __init__(self, real_syncer):
            self._real_syncer = real_syncer

        async def new_sync_headers(self, max_batch_size):
            async for headers in self._real_syncer.new_sync_headers(1):
                yield headers
                await self._real_syncer.sleep(1)
                raise Exception("This should always get cancelled quickly, say within 1s")

    class HeaderSyncer_PauseThenRest:
        def __init__(self, real_syncer):
            self._real_syncer = real_syncer
            self._ready = asyncio.Event()
            self._headers_requested = asyncio.Event()

        async def new_sync_headers(self, max_batch_size):
            self._headers_requested.set()
            await self._ready.wait()
            async for headers in self._real_syncer.new_sync_headers(max_batch_size):
                yield headers

        def unpause(self):
            self._ready.set()

        async def until_headers_requested(self):
            await self._headers_requested.wait()

    def __init__(self, chain, db, peer_pool, token=None) -> None:
        super().__init__(token=token)
        self._chain = chain
        self._header_syncer = ETHHeaderChainSyncer(chain, db, peer_pool, self.cancel_token)
        self._single_header_syncer = self.HeaderSyncer_OnlyOne(self._header_syncer)
        self._paused_header_syncer = self.HeaderSyncer_PauseThenRest(self._header_syncer)
        self._draining_syncer = RegularChainBodySyncer(
            chain,
            db,
            peer_pool,
            self._single_header_syncer,
            SimpleBlockImporter(chain),
            self.cancel_token,
        )
        self._body_syncer = RegularChainBodySyncer(
            chain,
            db,
            peer_pool,
            self._paused_header_syncer,
            SimpleBlockImporter(chain),
            self.cancel_token,
        )

    async def _run(self) -> None:
        self.run_daemon(self._header_syncer)
        starting_header = await self._chain.coro_get_canonical_head()

        # want body_syncer to start early so that it thinks the genesis is the canonical head
        self.run_child_service(self._body_syncer)
        await self._paused_header_syncer.until_headers_requested()

        # now drain out the first header and save it to db
        self.run_child_service(self._draining_syncer)

        # wait until first syncer saves to db, then cancel it
        latest_header = starting_header
        while starting_header == latest_header:
            latest_header = await self._chain.coro_get_canonical_head()
            await self.sleep(0.03)
        await self._draining_syncer.cancel()

        # now permit the next syncer to begin
        self._paused_header_syncer.unpause()

        # run regular sync until cancelled
        await self.events.cancelled.wait()


@pytest.mark.asyncio
async def test_regular_syncer_fallback(request, event_loop, event_bus, chaindb_fresh, chaindb_20):
    """
    Test the scenario where a header comes in that's not in memory (but is in the DB)
    """
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        alice_headerdb=FakeAsyncHeaderDB(chaindb_fresh.db),
        bob_headerdb=FakeAsyncHeaderDB(chaindb_20.db))
    client = FallbackTesting_RegularChainSyncer(
        ByzantiumTestChain(chaindb_fresh.db),
        chaindb_fresh,
        MockPeerPoolWithConnectedPeers([client_peer]))
    server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

    async with run_peer_pool_event_server(
        event_bus, server_peer_pool, handler_type=ETHPeerPoolEventServer
    ), run_request_server(
        event_bus, FakeAsyncChainDB(chaindb_20.db)
    ):

        server_peer.logger.info("%s is serving 20 blocks", server_peer)
        client_peer.logger.info("%s is syncing up 20", client_peer)

        def finalizer():
            event_loop.run_until_complete(client.cancel())
            # Yield control so that client/server.run() returns, otherwise asyncio will complain.
            event_loop.run_until_complete(asyncio.sleep(0.1))
        request.addfinalizer(finalizer)

        asyncio.ensure_future(client.run())

        await wait_for_head(chaindb_fresh, chaindb_20.get_canonical_head())
        head = chaindb_fresh.get_canonical_head()
        assert head.state_root in chaindb_fresh.db


@pytest.mark.asyncio
async def test_light_syncer(request,
                            event_loop,
                            event_bus,
                            chaindb_fresh,
                            chaindb_20):
    client_peer, server_peer = await get_directly_linked_peers(
        request, event_loop,
        alice_peer_class=LESPeer,
        alice_headerdb=FakeAsyncHeaderDB(chaindb_fresh.db),
        bob_headerdb=FakeAsyncHeaderDB(chaindb_20.db))
    client = LightChainSyncer(
        ByzantiumTestChain(chaindb_fresh.db),
        chaindb_fresh,
        MockPeerPoolWithConnectedPeers([client_peer]))
    server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

    async with run_peer_pool_event_server(
        event_bus, server_peer_pool, handler_type=LESPeerPoolEventServer
    ), run_request_server(
        event_bus, FakeAsyncChainDB(chaindb_20.db), server_type=LightRequestServer
    ):

        server_peer.logger.info("%s is serving 20 blocks", server_peer)
        client_peer.logger.info("%s is syncing up 20", client_peer)

        def finalizer():
            event_loop.run_until_complete(client.cancel())
            # Yield control so that client/server.run() returns, otherwise asyncio will complain.
            event_loop.run_until_complete(asyncio.sleep(0.1))
        request.addfinalizer(finalizer)

        asyncio.ensure_future(client.run())

        await wait_for_head(chaindb_fresh, chaindb_20.get_canonical_head())


@pytest.fixture
def leveldb_20():
    yield from load_fixture_db(DBFixture.twenty_pow_headers)


@pytest.fixture
def leveldb_1000():
    yield from load_fixture_db(DBFixture.thousand_pow_headers)


@pytest.fixture
def chaindb_1000(leveldb_1000):
    chain = load_mining_chain(FakeAsyncAtomicDB(leveldb_1000))
    assert chain.chaindb.get_canonical_head().block_number == 1000
    return chain.chaindb


@pytest.fixture
def chaindb_20(leveldb_20):
    chain = load_mining_chain(FakeAsyncAtomicDB(leveldb_20))
    assert chain.chaindb.get_canonical_head().block_number == 20
    return chain.chaindb


@pytest.fixture
def chaindb_fresh():
    chain = load_mining_chain(FakeAsyncAtomicDB())
    assert chain.chaindb.get_canonical_head().block_number == 0
    return chain.chaindb


async def wait_for_head(headerdb, header, timeout=None):
    # A full header sync may involve several round trips, so we must be willing to wait a little
    # bit for them.
    if timeout is None:
        timeout = 3

    async def wait_loop():
        while headerdb.get_canonical_head() != header:
            await asyncio.sleep(0.1)
    await asyncio.wait_for(wait_loop(), timeout)
