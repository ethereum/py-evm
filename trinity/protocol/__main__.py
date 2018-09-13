import argparse
import asyncio
import logging
import signal
from typing import (
    cast,
    Type,
    Union,
)

from eth.chains.mainnet import MainnetChain, MAINNET_GENESIS_HEADER, MAINNET_VM_CONFIGURATION
from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER, ROPSTEN_VM_CONFIGURATION
from eth.db.backends.memory import MemoryDB
from eth.tools.logging import TRACE_LEVEL_NUM

from p2p import ecies
from p2p.kademlia import Node

from trinity.protocol.common.context import ChainContext
from trinity.protocol.eth.peer import ETHPeer, ETHPeerPool
from trinity.protocol.les.peer import LESPeer, LESPeerPool

from tests.trinity.core.integration_test_helpers import FakeAsyncHeaderDB, connect_to_peers_loop


def _test() -> None:
    """
    Create a Peer instance connected to a local geth instance and log messages exchanged with it.

    Use the following command line to run geth:

        ./build/bin/geth -vmodule p2p=4,p2p/discv5=0,eth/*=0 \
          -nodekeyhex 45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8 \
          -testnet -lightserv 90
    """
    logging.basicConfig(level=TRACE_LEVEL_NUM, format='%(asctime)s %(levelname)s: %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-enode', type=str, help="The enode we should connect to", required=True)
    parser.add_argument('-light', action='store_true', help="Connect as a light node")
    args = parser.parse_args()

    peer_class: Union[Type[ETHPeer], Type[LESPeer]]
    pool_class: Union[Type[ETHPeerPool], Type[LESPeerPool]]

    if args.light:
        peer_class = LESPeer
        pool_class = LESPeerPool
    else:
        peer_class = ETHPeer
        pool_class = ETHPeerPool

    if args.mainnet:
        network_id = MainnetChain.network_id
        vm_config = MAINNET_VM_CONFIGURATION
        genesis = MAINNET_GENESIS_HEADER
    else:
        network_id = RopstenChain.network_id
        vm_config = ROPSTEN_VM_CONFIGURATION
        genesis = ROPSTEN_GENESIS_HEADER

    headerdb = FakeAsyncHeaderDB(MemoryDB())
    headerdb.persist_header(genesis)
    loop = asyncio.get_event_loop()
    nodes = [Node.from_uri(args.enode)]

    context = ChainContext(
        headerdb=headerdb,
        network_id=network_id,
        vm_configuration=vm_config,
    )
    peer_pool = pool_class(
        privkey=ecies.generate_privkey(),
        context=context,
    )

    asyncio.ensure_future(peer_pool.run())
    peer_pool.run_task(connect_to_peers_loop(peer_pool, nodes))

    async def request_stuff() -> None:
        # Request some stuff from ropsten's block 2440319
        # (https://ropsten.etherscan.io/block/2440319), just as a basic test.
        nonlocal peer_pool
        while not peer_pool.connected_nodes:
            peer_pool.logger.info("Waiting for peer connection...")
            await asyncio.sleep(0.2)
        peer = peer_pool.highest_td_peer
        headers = await cast(ETHPeer, peer).requests.get_block_headers(2440319, max_headers=100)
        hashes = tuple(header.hash for header in headers)
        if peer_class == ETHPeer:
            peer = cast(ETHPeer, peer)
            peer.sub_proto.send_get_block_bodies(hashes)
            peer.sub_proto.send_get_receipts(hashes)
        else:
            peer = cast(LESPeer, peer)
            request_id = 1
            peer.sub_proto.send_get_block_bodies(list(hashes), request_id + 1)
            peer.sub_proto.send_get_receipts(hashes[0], request_id + 2)

    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint() -> None:
        await sigint_received.wait()
        await peer_pool.cancel()
        loop.stop()

    asyncio.ensure_future(exit_on_sigint())
    asyncio.ensure_future(request_stuff())
    loop.set_debug(True)
    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    _test()
