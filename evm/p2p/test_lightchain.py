import asyncio
import os

import pytest

import rlp
from rlp import sedes

from evm.chains.mainnet import (
    MAINNET_NETWORK_ID,
    MAINNET_VM_CONFIGURATION,
)
from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.rlp.headers import BlockHeader
from evm.p2p import ecies
from evm.p2p.les import (
    LESProtocol,
    Announce,
    BlockHeaders,
    GetBlockHeaders,
    Status,
)
from evm.p2p.lightchain import LightChain
from evm.p2p.peer import LESPeer
from evm.p2p.test_peer import (
    get_directly_linked_peers,
    get_fresh_mainnet_chaindb,
)


# A full header sync may involve several round trips, so we must be willing to wait a little bit
# for them.
HEADER_SYNC_TIMEOUT = 3


@pytest.mark.asyncio
async def test_incremental_header_sync(request, event_loop, chaindb_mainnet_100):
    # Here, server will be a peer with a pre-populated chaindb, and we'll use it to send Announce
    # msgs to the client, which will then ask the server for any headers it's missing until their
    # chaindbs are in sync.
    light_chain, client, server = await get_lightchain_with_peers(
        request, event_loop, get_fresh_mainnet_chaindb())

    # We start the client/server with fresh chaindbs above because we don't want them to start
    # syncing straight away -- instead we want to manually trigger incremental syncs by having the
    # server send Announce messages. We're now ready to give our server a populated chaindb.
    server.chaindb = chaindb_mainnet_100

    # The server now announces block #10 as the new head...
    server.send_announce(head_number=10)

    # ... and we wait for the client to process that and request all headers it's missing up to
    # block #10.
    header_10 = server.chaindb.get_canonical_block_header_by_number(10)
    await wait_for_head(light_chain.chaindb, header_10)
    assert_canonical_chains_are_equal(light_chain.chaindb, server.chaindb, 10)

    # Now the server announces block 100 as its current head...
    server.send_announce(head_number=100)

    # ... and the client should then fetch headers from 10-100.
    header_100 = server.chaindb.get_canonical_block_header_by_number(100)
    await wait_for_head(light_chain.chaindb, header_100)
    assert_canonical_chains_are_equal(light_chain.chaindb, server.chaindb, 100)


@pytest.mark.asyncio
async def test_full_header_sync_and_reorg(request, event_loop, chaindb_mainnet_100):
    # Here we create our server with a populated chaindb, so upon startup it will announce its
    # chain head and the client will fetch all headers
    light_chain, client, server = await get_lightchain_with_peers(
        request, event_loop, chaindb_mainnet_100)

    # ... and our client should then fetch all headers.
    head = server.chaindb.get_canonical_head()
    await wait_for_head(light_chain.chaindb, head)
    assert_canonical_chains_are_equal(light_chain.chaindb, server.chaindb, head.block_number)

    head_parent = server.chaindb.get_block_header_by_hash(head.parent_hash)
    difficulty = head.difficulty + 1
    new_head = BlockHeader.from_parent(
        head_parent, head_parent.gas_limit, difficulty=difficulty,
        timestamp=head.timestamp, coinbase=head.coinbase)
    server.chaindb.persist_header_to_db(new_head)
    assert server.chaindb.get_canonical_head() == new_head
    server.send_announce(head_number=head.block_number, reorg_depth=1)

    await wait_for_head(light_chain.chaindb, new_head)
    assert_canonical_chains_are_equal(light_chain.chaindb, server.chaindb, new_head.block_number)


@pytest.mark.asyncio
async def test_header_sync_with_multi_peers(request, event_loop, chaindb_mainnet_100):
    # In this test we start with one of our peers announcing block #100, and we sync all
    # headers up to that...
    light_chain, client, server = await get_lightchain_with_peers(
        request, event_loop, chaindb_mainnet_100)

    head = server.chaindb.get_canonical_head()
    await wait_for_head(light_chain.chaindb, head)
    assert_canonical_chains_are_equal(light_chain.chaindb, server.chaindb, head.block_number)

    # Now a second peer comes along and announces block #100 as well, but it's different
    # from the one we already have, so we need to fetch that too. And since it has a higher total
    # difficulty than the current head, it will become our new chain head.
    server2_chaindb = server.chaindb
    head_parent = server2_chaindb.get_block_header_by_hash(head.parent_hash)
    difficulty = head.difficulty + 1
    new_head = BlockHeader.from_parent(
        head_parent, head_parent.gas_limit, difficulty=difficulty,
        timestamp=head.timestamp, coinbase=head.coinbase)
    server2_chaindb.persist_header_to_db(new_head)
    assert server2_chaindb.get_canonical_head() == new_head
    client2, server2 = await get_client_and_server_peer_pair(
        request,
        event_loop,
        client_chaindb=light_chain.chaindb,
        client_received_msg_callback=light_chain.msg_handler,
        server_chaindb=server2_chaindb)

    await wait_for_head(light_chain.chaindb, new_head)
    assert_canonical_chains_are_equal(light_chain.chaindb, server2.chaindb, new_head.block_number)


class LESProtocolServer(LESProtocol):
    _commands = [Status, Announce, BlockHeaders, GetBlockHeaders]

    def send_announce(self, block_hash, block_number, total_difficulty, reorg_depth):
        data = {
            'head_hash': block_hash,
            'head_number': block_number,
            'head_td': total_difficulty,
            'reorg_depth': reorg_depth,
            'params': [],
        }
        header, body = Announce(self.cmd_id_offset).encode(data)
        self.send(header, body)

    def send_block_headers(self, headers, buffer_value, request_id):
        data = {
            'request_id': request_id,
            'headers': headers,
            'buffer_value': buffer_value,
        }
        header, body = BlockHeaders(self.cmd_id_offset).encode(data)
        self.send(header, body)


class LESPeerServer(LESPeer):
    """A LESPeer that can send announcements and responds to GetBlockHeaders msgs.

    Used to test our LESPeer implementation. Tests should call .send_announce(), optionally
    specifying a block number to use as the chain's head and then use the helper function
    wait_for_head() to wait until the client peer has synced all headers up to the announced head.
    """
    conn_idle_timeout = 2
    reply_timeout = 1
    max_headers_fetch = 20
    _supported_sub_protocols = [LESProtocolServer]
    _head_number = None

    @property
    def head_number(self):
        if self._head_number is not None:
            return self._head_number
        else:
            return self.chaindb.get_canonical_head().block_number

    def send_announce(self, head_number=None, reorg_depth=0):
        if head_number is not None:
            self._head_number = head_number
        header = self.chaindb.get_canonical_block_header_by_number(self.head_number)
        total_difficulty = self.chaindb.get_score(header.hash)
        self.les_proto.send_announce(
            header.hash, header.block_number, total_difficulty, reorg_depth)

    def process_msg(self, msg):
        cmd, decoded = super(LESPeerServer, self).process_msg(msg)
        if isinstance(cmd, GetBlockHeaders):
            self.handle_get_block_headers(decoded)
        return cmd, decoded

    def handle_get_block_headers(self, msg):
        query = msg['query']
        block_number = query.block_number_or_hash
        assert isinstance(block_number, int)  # For now we only support block numbers
        if query.reverse:
            start = max(0, query.block - query.max_headers)
            # Shift our range() limits by 1 because we want to include the requested block number
            # in the list of block numbers.
            block_numbers = reversed(range(start + 1, block_number + 1))
        else:
            end = min(self.head_number + 1, block_number + query.max_headers)
            block_numbers = range(block_number, end)

        headers = tuple(
            self.chaindb.get_canonical_block_header_by_number(i)
            for i in block_numbers
        )
        self.les_proto.send_block_headers(headers, buffer_value=0, request_id=msg['request_id'])


async def get_client_and_server_peer_pair(
        request, event_loop, client_chaindb, client_received_msg_callback, server_chaindb):
    """Return a client/server peer pair with the given chain DBs.

    The client peer will be an instance of LESPeer, configured with the given chaindb and
    received_msg_callback, so that we can test LightChain's header syncing.

    The server peer will be an instance of LESPeerServer (which is necessary because we want a
    peer that can respond to GetBlockHeaders requests), configured only with the given chaindb but
    no received_msg_callback.
    """
    server_received_msg_callback = None
    client, server = await get_directly_linked_peers(
        LESPeer, client_chaindb, client_received_msg_callback,
        LESPeerServer, server_chaindb, server_received_msg_callback)
    asyncio.ensure_future(client.start())
    asyncio.ensure_future(server.start())

    def finalizer():
        async def afinalizer():
            await client.stop()
            await server.stop()
        event_loop.run_until_complete(afinalizer())
    request.addfinalizer(finalizer)

    return client, server


async def get_lightchain_with_peers(request, event_loop, server_peer_chaindb):
    """Return a LightChainForTests instance with a client/server peer pair.

    The server is a LESPeerServer instance that can be used to send Announce and BlockHeaders
    messages, and the client will be configured with the LightChain's msg_handler so that a sync
    request is added to the LightChain's queue every time a new Announce message is received.
    """
    chaindb = get_fresh_mainnet_chaindb()
    light_chain = LightChainForTests(chaindb)
    asyncio.ensure_future(light_chain.run())
    await asyncio.sleep(0)  # Yield control to give the LightChain a chance to start

    def finalizer():
        event_loop.run_until_complete(light_chain.stop())

    request.addfinalizer(finalizer)

    client, server = await get_client_and_server_peer_pair(
        request,
        event_loop,
        client_chaindb=chaindb,
        client_received_msg_callback=light_chain.msg_handler,
        server_chaindb=server_peer_chaindb,
    )
    return light_chain, client, server


class MockPeerPool:

    def __init__(self, *args, **kwargs):
        pass

    async def run(self):
        pass

    async def stop(self):
        pass


LightChainForTests = LightChain.configure(
    'LightChainForTests',
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=MAINNET_NETWORK_ID,
    privkey=ecies.generate_privkey(),
    peer_pool_class=MockPeerPool,
)


def assert_canonical_chains_are_equal(chaindb1, chaindb2, block_number=None):
    """Assert that the canonical chains in both DBs are identical up to block_number."""
    if block_number is None:
        block_number = chaindb1.get_canonical_head().block_number
        assert block_number == chaindb2.get_canonical_head().block_number
    for i in range(0, block_number + 1):
        assert chaindb1.get_canonical_block_header_by_number(i) == (
            chaindb2.get_canonical_block_header_by_number(i))


@pytest.fixture
def chaindb_mainnet_100():
    """Return a chaindb with mainnet headers numbered from 0 to 100."""
    here = os.path.dirname(__file__)
    headers_rlp = open(os.path.join(here, 'testdata', 'sample_1000_headers_rlp'), 'r+b').read()
    headers = rlp.decode(headers_rlp, sedes=sedes.CountableList(BlockHeader))
    chaindb = BaseChainDB(MemoryDB())
    for i in range(0, 101):
        chaindb.persist_header_to_db(headers[i])
    return chaindb


async def wait_for_head(chaindb, header):
    async def wait_loop():
        while chaindb.get_canonical_head() != header:
            await asyncio.sleep(0.1)
    await asyncio.wait_for(wait_loop(), HEADER_SYNC_TIMEOUT)
