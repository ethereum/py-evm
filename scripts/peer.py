"""Connect to the given enode and request some arbitrary data from it.

Run with `python -m scripts.peer -enode <enode>`.

By default connects as a ROPSTEN peer using the ETH protocol.
"""
import argparse
import asyncio
import logging
import signal
from typing import (
    cast,
    Type,
    Union,
)

from eth_typing import BlockNumber
from eth_utils import DEBUG2_LEVEL_NUM

from eth.chains.mainnet import MainnetChain, MAINNET_GENESIS_HEADER, MAINNET_VM_CONFIGURATION
from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER, ROPSTEN_VM_CONFIGURATION
from eth.db.atomic import AtomicDB
from eth.db.backends.memory import MemoryDB

from p2p import ecies
from p2p.constants import DEVP2P_V5
from p2p.kademlia import Node

from trinity.db.eth1.header import AsyncHeaderDB
from trinity.protocol.common.context import ChainContext
from trinity.protocol.eth.peer import ETHPeer, ETHPeerPool
from trinity.protocol.les.peer import LESPeer, LESPeerPool
from trinity._utils.version import construct_trinity_client_identifier

from tests.core.integration_test_helpers import connect_to_peers_loop


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-enode', type=str, help="The enode we should connect to", required=True)
    parser.add_argument('-mainnet', action='store_true')
    parser.add_argument('-light', action='store_true', help="Connect as a light node")
    parser.add_argument('-debug', action="store_true")
    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = DEBUG2_LEVEL_NUM
    logging.basicConfig(
        level=log_level, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')

    peer_class: Union[Type[ETHPeer], Type[LESPeer]]
    pool_class: Union[Type[ETHPeerPool], Type[LESPeerPool]]

    if args.light:
        peer_class = LESPeer
        pool_class = LESPeerPool
    else:
        peer_class = ETHPeer
        pool_class = ETHPeerPool

    if args.mainnet:
        chain_id = MainnetChain.chain_id
        vm_config = MAINNET_VM_CONFIGURATION
        genesis = MAINNET_GENESIS_HEADER
    else:
        chain_id = RopstenChain.chain_id
        vm_config = ROPSTEN_VM_CONFIGURATION
        genesis = ROPSTEN_GENESIS_HEADER

    headerdb = AsyncHeaderDB(AtomicDB(MemoryDB()))
    headerdb.persist_header(genesis)
    loop = asyncio.get_event_loop()
    nodes = [Node.from_uri(args.enode)]

    context = ChainContext(
        headerdb=headerdb,
        network_id=chain_id,
        vm_configuration=vm_config,
        client_version_string=construct_trinity_client_identifier(),
        listen_port=30309,
        p2p_version=DEVP2P_V5,
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
        headers = await cast(ETHPeer, peer).eth_api.get_block_headers(
            BlockNumber(2440319),
            max_headers=100
        )
        hashes = tuple(header.hash for header in headers)
        if peer_class == ETHPeer:
            peer = cast(ETHPeer, peer)
            peer.eth_api.send_get_block_bodies(hashes)
            peer.eth_api.send_get_receipts(hashes)
        else:
            peer = cast(LESPeer, peer)
            peer.les_api.send_get_block_bodies(list(hashes))
            peer.les_api.send_get_receipts(hashes[0])

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
    _main()
