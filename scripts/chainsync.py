"""Run the chain syncer, storing data in the given db dir.

Run with `python -m scripts.chainsync -db <path>`.
"""
import argparse
import asyncio
import logging
from pathlib import Path
import signal
from typing import (
    cast,
    Type,
    Union,
)

from eth_typing import BlockNumber

from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER, ROPSTEN_VM_CONFIGURATION
from eth.chains.mainnet import MainnetChain, MAINNET_GENESIS_HEADER, MAINNET_VM_CONFIGURATION
from eth.db.atomic import AtomicDB
from eth.db.backends.level import LevelDB
from eth.exceptions import HeaderNotFound

from p2p import ecies
from p2p.constants import DEVP2P_V5
from p2p.kademlia import Node
from p2p.service import BaseService

from trinity.constants import DEFAULT_PREFERRED_NODES
from trinity.db.eth1.chain import AsyncChainDB
from trinity.db.eth1.header import AsyncHeaderDB
from trinity.protocol.common.context import ChainContext
from trinity.protocol.eth.peer import ETHPeerPool
from trinity.protocol.les.peer import LESPeerPool

from trinity.sync.full.chain import RegularChainSyncer
from trinity.sync.light.chain import LightChainSyncer
from trinity.tools.chain import AsyncMainnetChain, AsyncRopstenChain
from trinity._utils.chains import load_nodekey
from trinity._utils.version import construct_trinity_client_identifier

from tests.core.integration_test_helpers import connect_to_peers_loop


def _test() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-light', action="store_true")
    parser.add_argument('-nodekey', type=str)
    parser.add_argument('-enode', type=str, required=False, help="The enode we should connect to")
    parser.add_argument('-debug', action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    loop = asyncio.get_event_loop()

    base_db = LevelDB(args.db)
    headerdb = AsyncHeaderDB(AtomicDB(base_db))
    chaindb = AsyncChainDB(AtomicDB(base_db))
    try:
        genesis = chaindb.get_canonical_block_header_by_number(BlockNumber(0))
    except HeaderNotFound:
        genesis = ROPSTEN_GENESIS_HEADER
        chaindb.persist_header(genesis)

    peer_pool_class: Type[Union[ETHPeerPool, LESPeerPool]] = ETHPeerPool
    if args.light:
        peer_pool_class = LESPeerPool

    chain_class: Union[Type[AsyncRopstenChain], Type[AsyncMainnetChain]]
    if genesis.hash == ROPSTEN_GENESIS_HEADER.hash:
        chain_id = RopstenChain.chain_id
        vm_config = ROPSTEN_VM_CONFIGURATION
        chain_class = AsyncRopstenChain
    elif genesis.hash == MAINNET_GENESIS_HEADER.hash:
        chain_id = MainnetChain.chain_id
        vm_config = MAINNET_VM_CONFIGURATION  # type: ignore
        chain_class = AsyncMainnetChain
    else:
        raise RuntimeError("Unknown genesis: %s", genesis)

    if args.nodekey:
        privkey = load_nodekey(Path(args.nodekey))
    else:
        privkey = ecies.generate_privkey()

    context = ChainContext(
        headerdb=headerdb,
        network_id=chain_id,
        vm_configuration=vm_config,
        client_version_string=construct_trinity_client_identifier(),
        listen_port=30309,
        p2p_version=DEVP2P_V5,
    )

    peer_pool = peer_pool_class(privkey=privkey, context=context)

    if args.enode:
        nodes = tuple([Node.from_uri(args.enode)])
    else:
        nodes = DEFAULT_PREFERRED_NODES[chain_id]

    asyncio.ensure_future(peer_pool.run())
    peer_pool.run_task(connect_to_peers_loop(peer_pool, nodes))
    chain = chain_class(base_db)
    syncer: BaseService = None
    if args.light:
        syncer = LightChainSyncer(chain, headerdb, cast(LESPeerPool, peer_pool))
    else:
        syncer = RegularChainSyncer(chain, chaindb, cast(ETHPeerPool, peer_pool))
    syncer.logger.setLevel(log_level)

    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, sigint_received.set)

    async def exit_on_sigint() -> None:
        await sigint_received.wait()
        await peer_pool.cancel()
        await syncer.cancel()
        loop.stop()

    async def run() -> None:
        await syncer.run()
        syncer.logger.info("run() finished, exiting")
        sigint_received.set()

    # loop.set_debug(True)
    asyncio.ensure_future(exit_on_sigint())
    asyncio.ensure_future(run())
    loop.run_forever()
    loop.close()


def _run_test(profile: bool) -> None:
    import cProfile, pstats  # noqa

    if profile:
        cProfile.run('_test()', 'stats')
        pstats.Stats('stats').strip_dirs().sort_stats('cumulative').print_stats(50)
    else:
        _test()


if __name__ == "__main__":
    _run_test(profile=False)
