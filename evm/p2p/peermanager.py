import asyncio
import logging

from eth_keys import keys
from eth_utils import decode_hex

from evm.p2p.constants import HANDSHAKE_TIMEOUT
from evm.p2p.exceptions import (
    PeerDisconnected,
    UnreachablePeer,
    UselessPeer,
)
from evm.p2p import ecies
from evm.p2p.peer import (
    handshake,
    LESPeer,
)


class PeerManager:
    logger = logging.getLogger("evm.p2p.peer.PeerManager")
    min_peers = 5
    # Number of seconds we sleep in the discovery loop once we are connected to at least
    # min_peers.
    discovery_sleep = 3

    def __init__(self, discovery, chaindb, network_id):
        self.discovery = discovery
        self.connected_nodes = {}
        self.chaindb = chaindb
        self.network_id = network_id
        # FIXME: Need a persistent DB to keep track of failed/successful peers or else every time
        # we start it takes ages to find peers that support les/1 and are on the same network as
        # us.
        self.failed_remotes = set()
        self.useless_remotes = set()
        self._seen_remotes = set()
        self._les_remotes = set()

    @property
    def privkey(self):
        return self.discovery.privkey

    def peer_disconnected(self, peer):
        if peer.remote in self.connected_nodes:
            self.connected_nodes.pop(peer.remote)

    async def run(self, loop):
        asyncio.ensure_future(self.reconnect_loop())
        await self.discovery_loop(loop)

    async def stop(self):
        # XXX: Commented out because on the fixed_nodes_loop we don't run discovery
        # self.discovery.stop()
        # Make a copy of the dict's values because we're going to mutate the dict when calling
        # peer.stop()
        connected_peers = list(self.connected_nodes.values())
        await asyncio.gather(
            *[peer.stop_and_wait_until_finished() for peer in connected_peers])

    async def fixed_nodes_loop(self, loop):
        good_nodes = [
            # Mainnet LES/1 nodes.
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

        if self.network_id == 3:
            good_nodes = [
                # Ropsten LES/1 nodes.
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

        while True:
            if len(self.connected_nodes) >= 3:
                self.logger.debug(
                    "Already connected to {} peers: {}; sleeping".format(
                        len(self.connected_nodes),
                        [remote for remote in self.connected_nodes.keys()]))
                await asyncio.sleep(20)
                continue

            for node in good_nodes:
                if node in self.connected_nodes:
                    self.logger.debug("Skipping {}, already connected".format(node))
                    continue
                self.logger.info("Connecting to {}".format(node))
                peer = await self.connect(node)
                if peer is not None:
                    asyncio.ensure_future(peer.start())
                    self.connected_nodes[peer.remote] = peer
            await asyncio.sleep(self.discovery_sleep)

    async def discovery_loop(self, loop):
        await self.discovery.listen(loop)
        await self.discovery.bootstrap()
        while True:
            if len(self.connected_nodes) >= self.min_peers:
                self.logger.info(
                    "Already connected to {} peers: {}; sleeping".format(
                        len(self.connected_nodes),
                        [remote for remote in self.connected_nodes.keys()]))
                await asyncio.sleep(self.discovery_sleep)
                continue

            self._log_remotes_stats()
            candidates = await self.discovery.lookup_random_node()
            peers = await asyncio.gather(
                *[self.connect(candidate) for candidate in candidates])
            for peer in peers:
                if peer is not None:
                    asyncio.ensure_future(peer.start())
                    self.connected_nodes[peer.remote] = peer

    # XXX: This is a hack
    async def reconnect_loop(self):
        while True:
            await asyncio.sleep(20)
            if len(self.connected_nodes) >= self.min_peers:
                continue
            peers = await asyncio.gather(
                *[self.connect(candidate) for candidate in self._les_remotes])
            for peer in peers:
                if peer is not None:
                    asyncio.ensure_future(peer.start())
                    self.connected_nodes[peer.remote] = peer

    def _log_remotes_stats(self):
        self.logger.info("Seen a total of {} peers".format(len(self._seen_remotes)))
        self.logger.info("Useless peers: {}".format(len(self.useless_remotes)))
        self.logger.info("Failed peers: {}".format(len(self.failed_remotes)))
        self.logger.info("Useful LES peers: {}: {}".format(
            len(self._les_remotes),
            ["{}({})".format(remote.address, remote.pubkey)
                for remote in self._les_remotes]))
        self.logger.info("Connected to {} peers".format(len(self.connected_nodes)))

    async def connect(self, remote):
        if remote in self.connected_nodes:
            self.logger.debug("Skipping {}; already connected to it".format(remote))
            return None
        elif remote in self.failed_remotes:
            self.logger.debug("Skipping failed node {}".format(remote))
            return None
        elif remote in self.useless_remotes:
            self.logger.debug("Skipping useless node {}".format(remote))
            return None

        # XXX: This is just for debugging
        self._seen_remotes.add(remote)
        try:
            peer = await asyncio.wait_for(
                handshake(remote, self.privkey, LESPeer, self.chaindb, self.network_id, self),
                HANDSHAKE_TIMEOUT)
            return peer
        except (UnreachablePeer, asyncio.TimeoutError) as e:
            self.logger.debug("Failed to connect to {}: {}".format(remote, e))
            self.failed_remotes.add(remote)
        except UselessPeer:
            self.logger.debug("No matching capabilities with {}".format(remote))
            self.useless_remotes.add(remote)
        except PeerDisconnected as e:
            self.logger.debug(
                "{} disconnected before completing handshake; reason: {}".format(remote, e))
        except Exception as e:
            self.logger.warn("Unexpected error during auth/p2p handhsake with {}: {}".format(
                remote, e))
        return None


if __name__ == "__main__":
    import argparse
    from evm.p2p import kademlia
    from evm.p2p import discovery
    from evm.db.backends.level import LevelDB
    from evm.db.backends.memory import MemoryDB
    from evm.db.chain import BaseChainDB
    from evm.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
    from evm.chains.mainnet import MainnetChain, MAINNET_GENESIS_HEADER

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str)
    parser.add_argument('-mainnet', action="store_true")
    args = parser.parse_args()
    genesis_header = ROPSTEN_GENESIS_HEADER
    chain_class = RopstenChain
    if args.mainnet:
        genesis_header = MAINNET_GENESIS_HEADER
        chain_class = MainnetChain
    if args.db is not None:
        chaindb = BaseChainDB(LevelDB(args.db))
    else:
        chaindb = BaseChainDB(MemoryDB())
        # Need to add the genesis header to the DB for when a peer does the LES handshake.
        chaindb.persist_header_to_db(genesis_header)

    listen_host = '0.0.0.0'
    listen_port = 30303
    bootstrap_nodes = [
        # Testnet bootnodes
        # b'enode://6ce05930c72abc632c58e2e4324f7c7ea478cec0ed4fa2528982cf34483094e9cbc9216e7aa349691242576d552a2a56aaeae426c5303ded677ce455ba1acd9d@13.84.180.240:30303',  # noqa: E501
        # b'enode://20c9ad97c081d63397d7b685a412227a40e23c8bdc6688c6f37e97cfbc22d2b4d1db1510d8f61e6a8866ad7f0e17c02b14182d37ea7c3c8b9c2683aeb6b733a1@52.169.14.227:30303',  # noqa: E501
        # Mainnet bootnodes
        b'enode://78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d@191.235.84.50:30303',  # noqa: E501
        b'enode://158f8aab45f6d19c6cbf4a089c2670541a8da11978a2f90dbf6a502a4a3bab80d288afdbeb7ec0ef6d92de563767f3b1ea9e8e334ca711e9f8e2df5a0385e8e6@13.75.154.138:30303',  # noqa: E501
        b'enode://1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082@52.74.57.123:30303',   # noqa: E501
    ]
    # Useful LES/1 peers for testnet (id==3)
    # ['Address(188.165.227.180:udp:30333|tcp:30333)(0xc8109b20aaac3cf8a793c1d1de505ca8b0a7e112734ef62f169bb4f2408af10ba31efce9fdb2b5b16499111a04a6204c331ffb8a131e6d19c79481884d162e3e)',
    # 'Address(51.15.218.125:udp:30303|tcp:30303)(0xa1ef9ba5550d5fac27f7cbd4e8d20a643ad75596f307c91cd6e7f85b548b8a6bf215cca436d6ee436d6135f9fe51398f8dd4c0bd6c6a0c332ccb41880f33ec12)',
    # 'Address(212.47.237.127:udp:30303|tcp:30303)(0xe006f0b2dc98e757468b67173295519e9b6d5ff4842772acb18fd055c620727ab23766c95b8ee1008dea9e8ef61e83b1515ddb3fb56dbfb9dbf1f463552a7c9f)',
    # 'Address(51.15.132.235:udp:30303|tcp:30303)(0xd40871fc3e11b2649700978e06acd68a24af54e603d4333faecb70926ca7df93baa0b7bf4e927fcad9a7c1c07f9b325b22f6d1730e728314d0e4e6523e5cebc2)']

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.getLogger("evm.p2p.peer.PeerManager").setLevel(logging.DEBUG)
    # logging.getLogger("evm.p2p.peer.Peer").setLevel(logging.DEBUG)
    # logging.getLogger("evm.p2p.protocol.Protocol").setLevel(logging.DEBUG)

    loop = asyncio.get_event_loop()
    # loop.set_debug(True)

    addr = kademlia.Address(listen_host, listen_port, listen_port)
    bootstrap_nodes = [kademlia.Node.from_uri(x) for x in bootstrap_nodes]
    discovery = discovery.DiscoveryProtocol(ecies.generate_privkey(), addr, bootstrap_nodes)
    manager = PeerManager(discovery, chaindb, chain_class.network_id)

    try:
        loop.run_until_complete(manager.fixed_nodes_loop(loop))
    except KeyboardInterrupt:
        pass

    loop.run_until_complete(manager.stop())
    loop.close()
