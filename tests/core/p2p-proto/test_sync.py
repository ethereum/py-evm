import asyncio
import uuid

from eth.db.atomic import AtomicDB
from eth.exceptions import HeaderNotFound
from eth.vm.forks.petersburg import PetersburgVM
from eth_utils import decode_hex
from lahja import ConnectionConfig, AsyncioEndpoint
from p2p.service import BaseService
import pytest

from trinity.db.eth1.chain import AsyncChainDB
from trinity.protocol.eth.peer import ETHPeerPoolEventServer
from trinity.sync.beam.importer import (
    make_pausing_beam_chain,
    BlockImportServer,
)
from trinity.protocol.eth.sync import ETHHeaderChainSyncer
from trinity.protocol.les.servers import LightRequestServer
from trinity.sync.common.checkpoint import Checkpoint
from trinity.sync.common.chain import (
    SimpleBlockImporter,
)
from trinity.sync.full.chain import FastChainSyncer, RegularChainSyncer, RegularChainBodySyncer

from trinity.protocol.les.peer import (
    LESPeerPoolEventServer,
)

from trinity.sync.full.state import StateDownloader
from trinity.sync.beam.chain import (
    BeamSyncer,
)
from trinity.sync.light.chain import LightChainSyncer

from trinity.tools.factories import (
    ChainContextFactory,
    ETHPeerPairFactory,
    LESV2PeerPairFactory,
)
from trinity.tools.chain import (
    ByzantiumTestChain,
    LatestTestChain,
)

from tests.core.integration_test_helpers import (
    DBFixture,
    load_fixture_db,
    load_mining_chain,
    run_peer_pool_event_server,
    run_request_server,
)
from tests.core.peer_helpers import (
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
    client_context = ChainContextFactory(headerdb__db=chaindb_fresh.db)
    server_context = ChainContextFactory(headerdb__db=chaindb_20.db)
    peer_pair = ETHPeerPairFactory(
        alice_peer_context=client_context,
        bob_peer_context=server_context,
        event_bus=event_bus,
    )
    async with peer_pair as (client_peer, server_peer):

        client_peer_pool = MockPeerPoolWithConnectedPeers([client_peer])
        client = FastChainSyncer(LatestTestChain(chaindb_fresh.db), chaindb_fresh, client_peer_pool)
        server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

        async with run_peer_pool_event_server(
            event_bus,
            server_peer_pool,
            handler_type=ETHPeerPoolEventServer,
        ), run_request_server(
            event_bus,
            AsyncChainDB(chaindb_20.db),
        ):

            server_peer.logger.info("%s is serving 20 blocks", server_peer)
            client_peer.logger.info("%s is syncing up 20", client_peer)

            # FastChainSyncer.run() will return as soon as it's caught up with the peer.
            await asyncio.wait_for(client.run(), timeout=5)

            head = chaindb_fresh.get_canonical_head()
            assert head == chaindb_20.get_canonical_head()

            # Now download the state for the chain's head.
            state_downloader = StateDownloader(
                chaindb_fresh, chaindb_fresh.db, head.state_root, client_peer_pool)
            await asyncio.wait_for(state_downloader.run(), timeout=5)

            assert head.state_root in chaindb_fresh.db


@pytest.mark.asyncio
async def test_skeleton_syncer(request, event_loop, event_bus, chaindb_fresh, chaindb_1000):

    client_context = ChainContextFactory(headerdb__db=chaindb_fresh.db)
    server_context = ChainContextFactory(headerdb__db=chaindb_1000.db)
    peer_pair = ETHPeerPairFactory(
        alice_peer_context=client_context,
        bob_peer_context=server_context,
        event_bus=event_bus,
    )
    async with peer_pair as (client_peer, server_peer):

        client_peer_pool = MockPeerPoolWithConnectedPeers([client_peer])
        client = FastChainSyncer(LatestTestChain(chaindb_fresh.db), chaindb_fresh, client_peer_pool)
        server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

        async with run_peer_pool_event_server(
            event_bus, server_peer_pool, handler_type=ETHPeerPoolEventServer
        ), run_request_server(
            event_bus, AsyncChainDB(chaindb_1000.db)
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
async def test_beam_syncer_with_checkpoint(
        request,
        event_loop,
        event_bus,
        chaindb_fresh,
        chaindb_churner):

    checkpoint = Checkpoint(
        block_hash=decode_hex('0x5b8d32e4aebda3da7bdf2f0588cb42256e2ed0c268efec71b38278df8488a263'),
        score=55,
    )

    await test_beam_syncer(
        request,
        event_loop,
        event_bus,
        chaindb_fresh,
        chaindb_churner,
        beam_to_block=66,
        checkpoint=checkpoint,
    )


# Identified tricky scenarios:
# - 66: Missing an account trie node required for account deletion trie fixups,
#       when "resuming" execution after completing all transactions
# - 68: If some storage saves succeed and some fail, you might get:
#       After persisting storage trie, a root node was not found.
#       State root for account 0x49361e4f811f49542f19d691cf5f79d39983e8e0 is missing for
#       hash 0x4d76d61d563099c7fa0088068bc7594d27334f5df2df43110bf86ff91dce5be6
# This test was reduced to a few cases for speed. To run the full suite, use
# range(1, 130) for beam_to_block. (and optionally follow the instructions at target_head)
@pytest.mark.asyncio
@pytest.mark.parametrize('beam_to_block', [1, 66, 68, 129])
async def test_beam_syncer(
        request,
        event_loop,
        event_bus,
        chaindb_fresh,
        chaindb_churner,
        beam_to_block,
        checkpoint=None):

    client_context = ChainContextFactory(headerdb__db=chaindb_fresh.db)
    server_context = ChainContextFactory(headerdb__db=chaindb_churner.db)
    peer_pair = ETHPeerPairFactory(
        alice_peer_context=client_context,
        bob_peer_context=server_context,
        event_bus=event_bus,
    )
    async with peer_pair as (client_peer, server_peer):

        # Need a name that will be unique per xdist-process, otherwise
        #   lahja IPC endpoints in each process will clobber each other
        unique_process_name = uuid.uuid4()

        # manually add endpoint for beam vm to make requests
        pausing_config = ConnectionConfig.from_name(f"PausingEndpoint-{unique_process_name}")

        # manually add endpoint for trie data gatherer to serve requests
        gatherer_config = ConnectionConfig.from_name(f"GathererEndpoint-{unique_process_name}")

        client_peer_pool = MockPeerPoolWithConnectedPeers([client_peer])
        server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

        async with run_peer_pool_event_server(
            event_bus, server_peer_pool, handler_type=ETHPeerPoolEventServer
        ), run_request_server(
            event_bus, AsyncChainDB(chaindb_churner.db)
        ), AsyncioEndpoint.serve(
            pausing_config
        ) as pausing_endpoint, AsyncioEndpoint.serve(gatherer_config) as gatherer_endpoint:

            client_chain = make_pausing_beam_chain(
                ((0, PetersburgVM), ),
                chain_id=999,
                db=chaindb_fresh.db,
                event_bus=pausing_endpoint,
                loop=event_loop,
            )

            client = BeamSyncer(
                client_chain,
                chaindb_fresh.db,
                AsyncChainDB(chaindb_fresh.db),
                client_peer_pool,
                gatherer_endpoint,
                force_beam_block_number=beam_to_block,
                checkpoint=checkpoint,
            )

            client_peer.logger.info("%s is serving churner blocks", client_peer)
            server_peer.logger.info("%s is syncing up churner blocks", server_peer)

            import_server = BlockImportServer(
                pausing_endpoint,
                client_chain,
                token=client.cancel_token,
            )
            asyncio.ensure_future(import_server.run())

            await pausing_endpoint.connect_to_endpoints(gatherer_config)
            asyncio.ensure_future(client.run())

            # We can sync at least 10 blocks in 1s at current speeds, (or reach the current one)
            # Trying to keep the tests short-ish. A fuller test could always set the target header
            #   to the chaindb_churner canonical head, and increase the timeout significantly
            target_block_number = min(beam_to_block + 10, 129)
            target_head = chaindb_churner.get_canonical_block_header_by_number(target_block_number)
            await wait_for_head(chaindb_fresh, target_head, sync_timeout=10)
            assert target_head.state_root in chaindb_fresh.db

            # first stop the import server, so it doesn't hang waiting for state data
            await import_server.cancel()
            await client.cancel()


@pytest.mark.asyncio
async def test_regular_syncer(request, event_loop, event_bus, chaindb_fresh, chaindb_20):
    client_context = ChainContextFactory(headerdb__db=chaindb_fresh.db)
    server_context = ChainContextFactory(headerdb__db=chaindb_20.db)
    peer_pair = ETHPeerPairFactory(
        alice_peer_context=client_context,
        bob_peer_context=server_context,
        event_bus=event_bus,
    )

    async with peer_pair as (client_peer, server_peer):

        client = RegularChainSyncer(
            ByzantiumTestChain(chaindb_fresh.db),
            chaindb_fresh,
            MockPeerPoolWithConnectedPeers([client_peer]))
        server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

        async with run_peer_pool_event_server(
            event_bus, server_peer_pool, handler_type=ETHPeerPoolEventServer
        ), run_request_server(
            event_bus, AsyncChainDB(chaindb_20.db)
        ):

            server_peer.logger.info("%s is serving 20 blocks", server_peer)
            client_peer.logger.info("%s is syncing up 20", client_peer)

            def finalizer():
                event_loop.run_until_complete(client.cancel())
                # Yield control so that client/server.run() returns, otherwise
                # asyncio will complain.
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
        self._header_syncer = ETHHeaderChainSyncer(chain, db, peer_pool, token=self.cancel_token)
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
    client_context = ChainContextFactory(headerdb__db=chaindb_fresh.db)
    server_context = ChainContextFactory(headerdb__db=chaindb_20.db)
    peer_pair = ETHPeerPairFactory(
        alice_peer_context=client_context,
        bob_peer_context=server_context,
        event_bus=event_bus,
    )

    async with peer_pair as (client_peer, server_peer):

        client = FallbackTesting_RegularChainSyncer(
            ByzantiumTestChain(chaindb_fresh.db),
            chaindb_fresh,
            MockPeerPoolWithConnectedPeers([client_peer]))
        server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

        async with run_peer_pool_event_server(
            event_bus, server_peer_pool, handler_type=ETHPeerPoolEventServer
        ), run_request_server(
            event_bus, AsyncChainDB(chaindb_20.db)
        ):

            server_peer.logger.info("%s is serving 20 blocks", server_peer)
            client_peer.logger.info("%s is syncing up 20", client_peer)

            def finalizer():
                event_loop.run_until_complete(client.cancel())
                # Yield control so that client/server.run() returns, otherwise
                # asyncio will complain.
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
    client_context = ChainContextFactory(headerdb__db=chaindb_fresh.db)
    server_context = ChainContextFactory(headerdb__db=chaindb_20.db)
    peer_pair = LESV2PeerPairFactory(
        alice_peer_context=client_context,
        bob_peer_context=server_context,
        event_bus=event_bus,
    )
    async with peer_pair as (client_peer, server_peer):

        client = LightChainSyncer(
            LatestTestChain(chaindb_fresh.db),
            chaindb_fresh,
            MockPeerPoolWithConnectedPeers([client_peer]))
        server_peer_pool = MockPeerPoolWithConnectedPeers([server_peer], event_bus=event_bus)

        async with run_peer_pool_event_server(
            event_bus, server_peer_pool, handler_type=LESPeerPoolEventServer
        ), run_request_server(
            event_bus, AsyncChainDB(chaindb_20.db), server_type=LightRequestServer
        ):

            server_peer.logger.info("%s is serving 20 blocks", server_peer)
            client_peer.logger.info("%s is syncing up 20", client_peer)

            def finalizer():
                event_loop.run_until_complete(client.cancel())
                # Yield control so that client/server.run() returns, otherwise
                # asyncio will complain.
                event_loop.run_until_complete(asyncio.sleep(0.1))
            request.addfinalizer(finalizer)

            asyncio.ensure_future(client.run())

            await wait_for_head(chaindb_fresh, chaindb_20.get_canonical_head())


@pytest.fixture
def leveldb_churner():
    yield from load_fixture_db(DBFixture.state_churner)


@pytest.fixture
def chaindb_churner(leveldb_churner):
    chain = load_mining_chain(AtomicDB(leveldb_churner))
    assert chain.chaindb.get_canonical_head().block_number == 129
    return chain.chaindb


async def wait_for_head(headerdb, header, sync_timeout=10):
    # A full header sync may involve several round trips, so we must be willing to wait a little
    # bit for them.

    async def wait_loop():
        header_at_block = None
        while header_at_block != header:
            try:
                header_at_block = headerdb.get_canonical_block_header_by_number(header.block_number)
            except HeaderNotFound:
                await asyncio.sleep(0.1)
            else:
                break
    await asyncio.wait_for(wait_loop(), sync_timeout)
