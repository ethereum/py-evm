import asyncio
import logging
import traceback
from typing import cast, Dict, List  # noqa: F401

from async_lru import alru_cache

from eth_keys import datatypes
from eth_keys import keys
from eth_utils import (
    decode_hex,
    encode_hex,
)

from evm.chains import Chain
from evm.db.chain import BaseChainDB
from evm.exceptions import (
    BlockNotFound,
)
from evm.rlp.blocks import BaseBlock
from evm.p2p.constants import HANDSHAKE_TIMEOUT
from evm.p2p import ecies
from evm.p2p.exceptions import (
    PeerConnectionLost,
    PeerDisconnected,
    UnreachablePeer,
    UselessPeer,
)
from evm.p2p import kademlia
from evm.p2p.peer import (
    handshake,
    LESPeer,
)
from evm.p2p.utils import gen_request_id


class PeerPool:
    """PeerPool attempts to keep connections to at least min_peers on the given network."""
    logger = logging.getLogger("evm.p2p.lightchain.PeerPool")
    peer_class = LESPeer
    _connect_loop_sleep = 2

    def __init__(self, chaindb: BaseChainDB, network_id: int, privkey: datatypes.PrivateKey,
                 min_peers: int = 2
                 ) -> None:
        self.chaindb = chaindb
        self.network_id = network_id
        self.privkey = privkey
        self.min_peers = min_peers
        self.connected_nodes = {}  # type: Dict[kademlia.Node, LESPeer]
        self._should_stop = asyncio.Event()
        self._finished = asyncio.Event()

    async def get_best_peer(self) -> LESPeer:
        """
        Return the peer with the highest announced block height.
        """
        while len(self.connected_nodes) == 0:
            await asyncio.sleep(0.5)

        def peer_block_height(peer):
            return peer.synced_block_height or -1

        # TODO: Should pick a random one in case there are multiple peers with the same block
        # height.
        return max(self.connected_nodes.values(), key=peer_block_height)

    async def run(self):
        while not self._should_stop.is_set():
            try:
                await self.maybe_connect_to_more_peers()
            except:  # noqa: E722
                # Most unexpected errors should be transient, so we log and restart from scratch.
                self.logger.error("Unexpected error (%s), restarting", traceback.format_exc())
                await self.stop_all_peers()
            # Wait self._connect_loop_sleep seconds, unless we're asked to stop.
            await asyncio.wait([self._should_stop.wait()], timeout=self._connect_loop_sleep)
        self._finished.set()

    async def stop_all_peers(self):
        self.logger.info("Stopping all peers ...")
        await asyncio.gather(
            *[peer.stop_and_wait_until_finished() for peer in self.connected_nodes.values()])

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
        try:
            peer = await asyncio.wait_for(
                handshake(remote, self.privkey, self.peer_class, self.chaindb, self.network_id),
                HANDSHAKE_TIMEOUT)
            return cast(LESPeer, peer)
        except (UnreachablePeer, asyncio.TimeoutError, PeerConnectionLost) as e:
            self.logger.debug("Could not complete handshake with %s: %s", remote, e)
        except UselessPeer:
            self.logger.debug("No matching capabilities with %s", remote)
        except PeerDisconnected as e:
            self.logger.debug(
                "%s disconnected before completing handshake; reason: %s", remote, e)
        except Exception:
            self.logger.warn(
                "Unexpected error during auth/p2p handhsake with %s: %s",
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
            self.logger.debug("Connecting to %s", node)
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
        self.logger.info("Peer finished: %s", peer)
        if peer.remote in self.connected_nodes:
            self.connected_nodes.pop(peer.remote)

    async def get_nodes_to_connect(self) -> List[kademlia.Node]:
        # TODO: This should use the Discovery service to lookup nodes to connect to, but our
        # current implementation only supports v4 and with that it takes an insane amount of time
        # to find any LES nodes with the same network ID as us, so for now we hard-code some nodes
        # that seem to have a good uptime.
        from evm.chains.ropsten import RopstenChain
        from evm.chains.mainnet import MainnetChain
        if self.network_id == MainnetChain.network_id:
            return [
                kademlia.Node(
                    keys.PublicKey(decode_hex("1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082")),  # noqa: E501
                    kademlia.Address("52.74.57.123", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d")),  # noqa: E501
                    kademlia.Address("191.235.84.50", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("ddd81193df80128880232fc1deb45f72746019839589eeb642d3d44efbb8b2dda2c1a46a348349964a6066f8afb016eb2a8c0f3c66f32fadf4370a236a4b5286")),  # noqa: E501
                    kademlia.Address("52.231.202.145", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("3f1d12044546b76342d59d4a05532c14b85aa669704bfe1f864fe079415aa2c02d743e03218e57a33fb94523adb54032871a6c51b2cc5514cb7c7e35b3ed0a99")),  # noqa: E501
                    kademlia.Address("13.93.211.84", 30303, 30303)),
            ]
        elif self.network_id == RopstenChain.network_id:
            return [
                kademlia.Node(
                    keys.PublicKey(decode_hex("88c2b24429a6f7683fbfd06874ae3f1e7c8b4a5ffb846e77c705ba02e2543789d66fc032b6606a8d8888eb6239a2abe5897ce83f78dcdcfcb027d6ea69aa6fe9")),  # noqa: E501
                    kademlia.Address("163.172.157.61", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("a1ef9ba5550d5fac27f7cbd4e8d20a643ad75596f307c91cd6e7f85b548b8a6bf215cca436d6ee436d6135f9fe51398f8dd4c0bd6c6a0c332ccb41880f33ec12")),  # noqa: E501
                    kademlia.Address("51.15.218.125", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("e80276aabb7682a4a659f4341c1199de79d91a2e500a6ee9bed16ed4ce927ba8d32ba5dea357739ffdf2c5bcc848d3064bb6f149f0b4249c1f7e53f8bf02bfc8")),  # noqa: E501
                    kademlia.Address("51.15.39.57", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("584c0db89b00719e9e7b1b5c32a4a8942f379f4d5d66bb69f9c7fa97fa42f64974e7b057b35eb5a63fd7973af063f9a1d32d8c60dbb4854c64cb8ab385470258")),  # noqa: E501
                    kademlia.Address("51.15.35.2", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("d40871fc3e11b2649700978e06acd68a24af54e603d4333faecb70926ca7df93baa0b7bf4e927fcad9a7c1c07f9b325b22f6d1730e728314d0e4e6523e5cebc2")),  # noqa: E501
                    kademlia.Address("51.15.132.235", 30303, 30303)),
                kademlia.Node(
                    keys.PublicKey(decode_hex("482484b9198530ee2e00db89791823244ca41dcd372242e2e1297dd06f6d8dd357603960c5ad9cc8dc15fcdf0e4edd06b7ad7db590e67a0b54f798c26581ebd7")),  # noqa: E501
                    kademlia.Address("51.15.75.138", 30303, 30303)),
            ]
        else:
            raise ValueError("Unknown network_id: %s", self.network_id)


class LightChain(Chain):
    # FIXME: Should be passed in by callers
    privkey = ecies.generate_privkey()
    # TODO:
    # 1. Implement a queue of requests and a distributor which picks items from that queue and
    # sends them to one of our peers, ensuring the selected peer has the info we want,
    # retrying on timeouts and respecting the flow control rules.

    def __init__(self, chaindb: BaseChainDB) -> None:
        super(LightChain, self).__init__(chaindb)
        self.peer_pool = PeerPool(chaindb, self.network_id, self.privkey)

    async def run(self):
        await self.peer_pool.run()

    async def stop(self):
        self.logger.info("Stopping ...")
        await self.peer_pool.stop()

    async def get_canonical_block_by_number(self, block_number: int) -> BaseBlock:
        try:
            block_hash = self.chaindb.lookup_block_hash(block_number)
        except KeyError:
            raise BlockNotFound(
                "No block with number {} found on local chain".format(block_number))
        return await self.get_block_by_hash(block_hash)

    @alru_cache(maxsize=1024)
    async def get_block_by_hash(self, block_hash: bytes) -> BaseBlock:
        peer = await self.peer_pool.get_best_peer()
        self.logger.debug("Fetching block %s from %s", encode_hex(block_hash), peer)
        request_id = gen_request_id()
        peer.les_proto.send_get_block_bodies([block_hash], request_id)
        reply = await peer.wait_for_reply(request_id)
        if len(reply['bodies']) == 0:
            raise BlockNotFound("No block with hash {} found".format(block_hash))
        body = reply['bodies'][0]
        # This will raise a BlockNotFound if we don't have the header in our DB, which is correct
        # because it means our peer doesn't know about it.
        header = self.chaindb.get_block_header_by_hash(block_hash)
        block_class = self.get_vm_class_for_block_number(header.block_number).get_block_class()
        return block_class(
            header=header,
            transactions=body.transactions,
            uncles=body.uncles,
            chaindb=self.chaindb,
        )


if __name__ == '__main__':
    import argparse
    from evm.chains.mainnet import (
        MAINNET_GENESIS_HEADER, MAINNET_VM_CONFIGURATION, MAINNET_NETWORK_ID)
    from evm.db.backends.level import LevelDB
    from evm.exceptions import CanonicalHeadNotFound

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.getLogger("evm.p2p.lightchain").setLevel(logging.DEBUG)

    GENESIS_HEADER = MAINNET_GENESIS_HEADER
    NETWORK_ID = MAINNET_NETWORK_ID
    DemoLightChain = LightChain.configure(
        'DemoLightChain',
        vm_configuration=MAINNET_VM_CONFIGURATION,
        network_id=NETWORK_ID,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    args = parser.parse_args()

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
