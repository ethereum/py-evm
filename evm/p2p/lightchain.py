import asyncio
import logging
import traceback
from typing import (  # noqa: F401
    Any,
    Callable,
    cast,
    Dict,
    List,
    Optional,
    Tuple,
)

from async_lru import alru_cache

import rlp
from eth_keys import datatypes
from eth_utils import (
    encode_hex,
)
from trie import HexaryTrie

from evm.chains import Chain
from evm.constants import GENESIS_BLOCK_NUMBER
from evm.db.chain import BaseChainDB
from evm.exceptions import (
    BlockNotFound,
)
from evm.rlp.accounts import Account
from evm.rlp.blocks import BaseBlock
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt
from evm.utils.keccak import keccak
from evm.p2p.constants import HANDSHAKE_TIMEOUT
from evm.p2p.discovery import DiscoveryProtocol
from evm.p2p.exceptions import (
    EmptyGetBlockHeadersReply,
    LESAnnouncementProcessingError,
    PeerConnectionLost,
    PeerDisconnected,
    StopRequested,
    TooManyTimeouts,
    UnreachablePeer,
    UselessPeer,
)
from evm.p2p import kademlia
from evm.p2p import les
from evm.p2p import protocol
from evm.p2p.peer import (  # noqa: F401
    BasePeer,
    handshake,
    LESPeer,
    _ReceivedMsgCallbackType,
)
from evm.p2p.utils import gen_request_id


class PeerPool:
    """PeerPool attempts to keep connections to at least min_peers on the given network."""
    logger = logging.getLogger("evm.p2p.lightchain.PeerPool")
    peer_class = LESPeer
    min_peers = 2
    _connect_loop_sleep = 2

    def __init__(self,
                 chaindb: BaseChainDB,
                 network_id: int,
                 privkey: datatypes.PrivateKey,
                 msg_handler: _ReceivedMsgCallbackType,
                 ) -> None:
        self.chaindb = chaindb
        self.network_id = network_id
        self.privkey = privkey
        self.msg_handler = msg_handler
        self.connected_nodes = {}  # type: Dict[kademlia.Node, LESPeer]
        self._should_stop = asyncio.Event()
        self._finished = asyncio.Event()
        addr = kademlia.Address('0.0.0.0', 30304, 30304)
        bootstrap_nodes = [
            kademlia.Node.from_uri(enode) for enode in [
                b"enode://1c7a64d76c0334b0418c004af2f67c50e36a3be60b5e4790bdac0439d21603469a85fad36f2473c9a80eb043ae60936df905fa28f1ff614c3e5dc34f15dcd2dc@40.118.3.223:30308",  # noqa: E501
                b"enode://0cc5f5ffb5d9098c8b8c62325f3797f56509bff942704687b6530992ac706e2cb946b90a34f1f19548cd3c7baccbcaea354531e5983c7d1bc0dee16ce4b6440b@40.118.3.223:30305",  # noqa: E501
            ]
        ]
        genesis = chaindb.get_canonical_block_header_by_number(GENESIS_BLOCK_NUMBER)
        topic = b"LES@" + encode_hex(genesis.hash[:8])[2:].encode()
        self.discovery = DiscoveryProtocol(privkey, addr, bootstrap_nodes, topic)

    async def run(self):
        self.logger.info("Running PeerPool...")
        asyncio.ensure_future(self.discovery.run())
        while not self._should_stop.is_set():
            try:
                await self.maybe_connect_to_more_peers()
            except:  # noqa: E722
                # Most unexpected errors should be transient, so we log and restart from scratch.
                self.logger.error("Unexpected error (%s), restarting", traceback.format_exc())
                await self.stop_all_peers()
            # Wait self._connect_loop_sleep seconds, unless we're asked to stop.
            await asyncio.wait([self._should_stop.wait()], timeout=self._connect_loop_sleep)
        self.discovery.stop()
        self._finished.set()

    async def stop_all_peers(self):
        self.logger.info("Stopping all peers ...")
        await asyncio.gather(
            *[peer.stop() for peer in self.connected_nodes.values()])

    async def stop(self):
        self._should_stop.set()
        await self.stop_all_peers()
        await self._finished.wait()

    async def connect(self, remote: kademlia.Node) -> LESPeer:
        """
        Connect to the given remote and return a Peer instance when successful.
        Returns None if the remote is unreachable, times out or is useless.
        """
        if remote in self.connected_nodes:
            self.logger.debug("Skipping %s; already connected to it", remote)
            return None
        expected_exceptions = (
            UnreachablePeer, asyncio.TimeoutError, PeerConnectionLost,
            UselessPeer, PeerDisconnected)
        try:
            self.logger.info("Connecting to %s...", remote)
            peer = await asyncio.wait_for(
                handshake(remote, self.privkey, self.peer_class, self.chaindb, self.network_id,
                          self.msg_handler),
                HANDSHAKE_TIMEOUT)
            return cast(LESPeer, peer)
        except expected_exceptions as e:
            self.logger.info("Could not complete handshake with %s: %s", remote, repr(e))
        except Exception:
            self.logger.warn("Unexpected error during auth/p2p handhsake with %s: %s",
                             remote, traceback.format_exc())
        return None

    async def maybe_connect_to_more_peers(self):
        """Connect to more peers if we're not yet connected to at least self.min_peers."""
        if len(self.connected_nodes) >= self.min_peers:
            self.logger.debug(
                "Already connected to %s peers: %s; sleeping",
                len(self.connected_nodes),
                [remote for remote in self.connected_nodes])
            return

        for node in await self.get_nodes_to_connect():
            # TODO: Consider changing connect() to raise an exception instead of returning None,
            # as discussed in
            # https://github.com/pipermerriam/py-evm/pull/139#discussion_r152067425
            peer = await self.connect(node)
            if peer is not None:
                self.logger.info("Successfully connected to %s", peer)
                self.connected_nodes[peer.remote] = peer
                asyncio.ensure_future(peer.start(finished_callback=self._peer_finished))

    def _peer_finished(self, peer: LESPeer) -> None:
        """Remove the given peer from our list of connected nodes.
        This is passed as a callback to be called when a peer finishes.
        """
        if peer.remote in self.connected_nodes:
            self.connected_nodes.pop(peer.remote)

    @property
    def peers(self) -> List[LESPeer]:
        return list(self.connected_nodes.values())

    async def get_nodes_to_connect(self) -> List[kademlia.Node]:
        while len(self.discovery.matching_nodes) == 0:
            await asyncio.sleep(2)
            self.logger.warn(
                "Discovery hasn't found any nodes with topic %s yet", self.discovery.topic)
        return list(self.discovery.matching_nodes)


class LightChain(Chain):
    logger = logging.getLogger("evm.p2p.lightchain.LightChain")
    privkey = None  # type: datatypes.PrivateKey
    max_consecutive_timeouts = 5
    peer_pool_class = PeerPool

    def __init__(self, chaindb: BaseChainDB) -> None:
        super(LightChain, self).__init__(chaindb)
        self.peer_pool = self.peer_pool_class(
            chaindb, self.network_id, self.privkey, self.msg_handler)
        self._announcement_queue = asyncio.Queue()  # type: asyncio.Queue[Tuple[LESPeer, les.HeadInfo]]  # noqa: E501
        self._last_processed_announcements = {}  # type: Dict[LESPeer, les.HeadInfo]
        self._latest_head_info = {}  # type: Dict[LESPeer, les.HeadInfo]
        self._should_stop = asyncio.Event()
        self._finished = asyncio.Event()

    def msg_handler(self, peer: BasePeer, cmd: protocol.Command,
                    announcement: protocol._DecodedMsgType) -> None:
        """The callback passed to BasePeer, called for every incoming message."""
        peer = cast(LESPeer, peer)
        if isinstance(cmd, (les.Announce, les.Status)):
            head_info = cmd.as_head_info(announcement)
            self._latest_head_info[peer] = head_info
            self._announcement_queue.put_nowait((peer, head_info))

    async def drop_peer(self, peer: LESPeer) -> None:
        self._last_processed_announcements.pop(peer, None)
        self._latest_head_info.pop(peer, None)
        await peer.stop()

    async def get_best_peer(self) -> LESPeer:
        """
        Return the peer with the highest announced block height.
        """
        while len(self.peer_pool.peers) == 0:
            await asyncio.sleep(0.5)

        def peer_block_height(peer: LESPeer):
            last_announced = self._last_processed_announcements.get(peer)
            if last_announced is None:
                return -1
            return last_announced.block_number

        # TODO: Should pick a random one in case there are multiple peers with the same block
        # height.
        return max(self.peer_pool.peers, key=peer_block_height)

    async def wait_for_announcement(self) -> Tuple[LESPeer, les.HeadInfo]:
        """Wait for a new announcement from any of our connected peers.

        Returns a tuple containing the LESPeer on which the announcement was received and the
        announcement info.

        Raises StopRequested when LightChain.stop() has been called.
        """
        should_stop = False

        async def wait_for_stop_event():
            nonlocal should_stop
            await self._should_stop.wait()
            should_stop = True

        # Wait for either a new announcement or the _should_stop event.
        done, pending = await asyncio.wait(
            [self._announcement_queue.get(), wait_for_stop_event()],
            return_when=asyncio.FIRST_COMPLETED)
        # The asyncio.wait() call above may return both tasks as done, but never both as pending,
        # although to be future-proof (in case more than 2 tasks are passed in to wait()), we
        # iterate over all pending tasks and cancel all of them.
        for task in pending:
            task.cancel()
        if should_stop:
            raise StopRequested()
        return done.pop().result()

    async def run(self) -> None:
        """Run the LightChain, ensuring headers are in sync with connected peers.

        Run our PeerPool to ensure we are always connected to some peers and then loop forever,
        waiting for announcements from connected peers and fetching new headers.

        If .stop() is called, we'll disconnect from all peers and return.
        """
        self.logger.info("Running LightChain...")
        asyncio.ensure_future(self.peer_pool.run())
        while True:
            try:
                peer, head_info = await self.wait_for_announcement()
            except StopRequested:
                self.logger.debug("Asked to stop, breaking out of run() loop")
                break

            try:
                await self.process_announcement(peer, head_info)
                self._last_processed_announcements[peer] = head_info
            except StopRequested:
                self.logger.debug("Asked to stop, breaking out of run() loop")
                break
            except LESAnnouncementProcessingError as e:
                self.logger.warn(repr(e))
                await self.drop_peer(peer)
            except Exception as e:
                self.logger.error(
                    "Unexpected error when processing announcement: %s", repr(e))
                await self.drop_peer(peer)

        self._finished.set()

    async def fetch_headers(self, start_block: int, peer: LESPeer) -> List[BlockHeader]:
        for i in range(self.max_consecutive_timeouts):
            if self._should_stop.is_set():
                raise StopRequested()
            try:
                return await peer.fetch_headers_starting_at(start_block)
            except asyncio.TimeoutError:
                self.logger.info(
                    "Timeout when fetching headers from %s (attempt %d of %d)",
                    peer, i + 1, self.max_consecutive_timeouts)
                # TODO: Figure out what's a good value to use here.
                await asyncio.sleep(0.5)
        raise TooManyTimeouts()

    async def get_sync_start_block(self, peer: LESPeer, head_info: les.HeadInfo) -> int:
        chain_head = self.chaindb.get_canonical_head()
        last_peer_announcement = self._last_processed_announcements.get(peer)
        if chain_head.block_number == GENESIS_BLOCK_NUMBER:
            start_block = GENESIS_BLOCK_NUMBER
        elif last_peer_announcement is None:
            # It's the first time we hear from this peer, need to figure out which headers to
            # get from it.  We can't simply fetch headers starting from our current head
            # number because there may have been a chain reorg, so we fetch some headers prior
            # to our head from the peer, and insert any missing ones in our DB, essentially
            # making our canonical chain identical to the peer's up to
            # chain_head.block_number.
            oldest_ancestor_to_consider = max(
                0, chain_head.block_number - peer.max_headers_fetch + 1)
            try:
                headers = await self.fetch_headers(oldest_ancestor_to_consider, peer)
            except EmptyGetBlockHeadersReply:
                raise LESAnnouncementProcessingError(
                    "No common ancestors found between us and {}".format(peer))
            except TooManyTimeouts:
                raise LESAnnouncementProcessingError(
                    "Too many timeouts when fetching headers from {}".format(peer))
            for header in headers:
                self.chaindb.persist_header_to_db(header)
            start_block = chain_head.block_number
        else:
            start_block = last_peer_announcement.block_number - head_info.reorg_depth
        return start_block

    # TODO: Distribute requests among our peers, ensuring the selected peer has the info we want
    # and respecting the flow control rules.
    async def process_announcement(self, peer: LESPeer, head_info: les.HeadInfo) -> None:
        if self.chaindb.header_exists(head_info.block_hash):
            self.logger.debug(
                "Skipping processing of %s from %s as head has already been fetched",
                head_info, peer)
            return

        start_block = await self.get_sync_start_block(peer, head_info)
        while start_block < head_info.block_number:
            # TODO: Need to check that the peer is not finished (peer._finished.is_set()), because
            # if they are we're going to get errors when trying to use them to make requests.
            try:
                # We should use "start_block + 1" here, but we always re-fetch the last synced
                # block to work around https://github.com/ethereum/go-ethereum/issues/15447
                batch = await self.fetch_headers(start_block, peer)
            except TooManyTimeouts:
                raise LESAnnouncementProcessingError(
                    "Too many timeouts when fetching headers from {}".format(peer))
            for header in batch:
                self.chaindb.persist_header_to_db(header)
                start_block = header.block_number
            self.logger.info("synced headers up to #%s", start_block)

    async def stop(self):
        self.logger.info("Stopping LightChain...")
        self._should_stop.set()
        await self.peer_pool.stop()
        await self._finished.wait()

    async def get_canonical_block_by_number(self, block_number: int) -> BaseBlock:
        """Return the block with the given number from the canonical chain.

        Raises BlockNotFound if it is not found.
        """
        try:
            block_hash = self.chaindb.lookup_block_hash(block_number)
        except KeyError:
            raise BlockNotFound(
                "No block with number {} found on local chain".format(block_number))
        return await self.get_block_by_hash(block_hash)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_block_by_hash(self, block_hash: bytes) -> BaseBlock:
        peer = await self.get_best_peer()
        try:
            header = self.chaindb.get_block_header_by_hash(block_hash)
        except BlockNotFound:
            self.logger.debug("Fetching header %s from %s", encode_hex(block_hash), peer)
            request_id = gen_request_id()
            max_headers = 1
            peer.les_proto.send_get_block_headers(block_hash, max_headers, request_id)
            reply = await peer.wait_for_reply(request_id)
            if len(reply['headers']) == 0:
                raise BlockNotFound("Peer {} has no block with hash {}".format(peer, block_hash))
            header = reply['headers'][0]

        self.logger.debug("Fetching block %s from %s", encode_hex(block_hash), peer)
        request_id = gen_request_id()
        peer.les_proto.send_get_block_bodies([block_hash], request_id)
        reply = await peer.wait_for_reply(request_id)
        if len(reply['bodies']) == 0:
            raise BlockNotFound("Peer {} has no block with hash {}".format(peer, block_hash))
        body = reply['bodies'][0]
        block_class = self.get_vm_class_for_block_number(header.block_number).get_block_class()
        transactions = [
            block_class.transaction_class.from_base_transaction(tx)
            for tx in body.transactions
        ]
        return block_class(
            header=header,
            transactions=transactions,
            uncles=body.uncles,
            chaindb=self.chaindb,
        )

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_receipts(self, block_hash: bytes) -> List[Receipt]:
        peer = await self.get_best_peer()
        self.logger.debug("Fetching %s receipts from %s", encode_hex(block_hash), peer)
        request_id = gen_request_id()
        peer.les_proto.send_get_receipts(block_hash, request_id)
        reply = await peer.wait_for_reply(request_id)
        if len(reply['receipts']) == 0:
            raise BlockNotFound("No block with hash {} found".format(block_hash))
        return reply['receipts'][0]

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_account(self, block_hash: bytes, address: bytes) -> Account:
        key = keccak(address)
        proof = await self._get_proof(block_hash, account_key=b'', key=key)
        block = await self.get_block_by_hash(block_hash)
        rlp_account = HexaryTrie.get_from_proof(block.header.state_root, key, proof)
        return rlp.decode(rlp_account, sedes=Account)

    async def _get_proof(self, block_hash: bytes, account_key: bytes, key: bytes,
                         from_level: int = 0) -> List[bytes]:
        peer = await self.get_best_peer()
        request_id = gen_request_id()
        peer.les_proto.send_get_proof(block_hash, account_key, key, from_level, request_id)
        reply = await peer.wait_for_reply(request_id)
        return reply['proof']

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_contract_code(self, block_hash: bytes, key: bytes) -> bytes:
        peer = await self.get_best_peer()
        request_id = gen_request_id()
        peer.les_proto.send_get_contract_code(block_hash, key, request_id)
        reply = await peer.wait_for_reply(request_id)
        if len(reply['codes']) == 0:
            return b''
        return reply['codes'][0]


if __name__ == '__main__':
    import argparse
    from evm.chains.mainnet import (
        MAINNET_GENESIS_HEADER, MAINNET_VM_CONFIGURATION, MAINNET_NETWORK_ID)
    from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER, ROPSTEN_NETWORK_ID
    from evm.db.backends.level import LevelDB
    from evm.exceptions import CanonicalHeadNotFound
    from evm.p2p import ecies

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.getLogger("evm.p2p.lightchain.LightChain").setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-mainnet', action="store_true")
    args = parser.parse_args()

    GENESIS_HEADER = ROPSTEN_GENESIS_HEADER
    NETWORK_ID = ROPSTEN_NETWORK_ID
    if args.mainnet:
        GENESIS_HEADER = MAINNET_GENESIS_HEADER
        NETWORK_ID = MAINNET_NETWORK_ID
    DemoLightChain = LightChain.configure(
        'DemoLightChain',
        privkey=ecies.generate_privkey(),
        vm_configuration=MAINNET_VM_CONFIGURATION,
        network_id=NETWORK_ID,
    )

    chaindb = BaseChainDB(LevelDB(args.db))
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # We're starting with a fresh DB.
        chain = DemoLightChain.from_genesis_header(chaindb, GENESIS_HEADER)
    else:
        # We're reusing an existing db.
        chain = DemoLightChain(chaindb)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(chain.run())
    except KeyboardInterrupt:
        pass

    loop.run_until_complete(chain.stop())
    loop.close()
