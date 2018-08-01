import asyncio
import logging
from typing import (
    Type,
    Union,
)

from eth.exceptions import HeaderNotFound

from p2p.peer import PeerPool

from .common.chain import BaseHeaderChainSyncer
from .full.chain import FastChainSyncer, RegularChainSyncer
from .light.chain import LightChainSyncer


def _test() -> None:
    import argparse
    from pathlib import Path
    import signal
    from p2p import ecies
    from p2p.kademlia import Node
    from p2p.peer import DEFAULT_PREFERRED_NODES
    from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER, ROPSTEN_VM_CONFIGURATION
    from eth.chains.mainnet import MainnetChain, MAINNET_GENESIS_HEADER, MAINNET_VM_CONFIGURATION
    from eth.db.backends.level import LevelDB
    from tests.p2p.integration_test_helpers import (
        FakeAsyncChainDB, FakeAsyncMainnetChain, FakeAsyncRopstenChain, FakeAsyncHeaderDB,
        connect_to_peers_loop)
    from trinity.protocol.eth.peer import ETHPeer  # noqa: F811
    from trinity.protocol.les.peer import LESPeer  # noqa: F811
    from trinity.utils.chains import load_nodekey

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-fast', action="store_true")
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
    headerdb = FakeAsyncHeaderDB(base_db)
    chaindb = FakeAsyncChainDB(base_db)
    try:
        genesis = chaindb.get_canonical_block_header_by_number(0)
    except HeaderNotFound:
        genesis = ROPSTEN_GENESIS_HEADER
        chaindb.persist_header(genesis)

    peer_class: Type[Union[ETHPeer, LESPeer]] = ETHPeer
    if args.light:
        peer_class = LESPeer

    if genesis.hash == ROPSTEN_GENESIS_HEADER.hash:
        network_id = RopstenChain.network_id
        vm_config = ROPSTEN_VM_CONFIGURATION  # type: ignore
        chain_class = FakeAsyncRopstenChain
    elif genesis.hash == MAINNET_GENESIS_HEADER.hash:
        network_id = MainnetChain.network_id
        vm_config = MAINNET_VM_CONFIGURATION  # type: ignore
        chain_class = FakeAsyncMainnetChain
    else:
        raise RuntimeError("Unknown genesis: %s", genesis)
    if args.nodekey:
        privkey = load_nodekey(Path(args.nodekey))
    else:
        privkey = ecies.generate_privkey()
    peer_pool = PeerPool(peer_class, headerdb, network_id, privkey, vm_config)
    if args.enode:
        nodes = tuple([Node.from_uri(args.enode)])
    else:
        nodes = DEFAULT_PREFERRED_NODES[network_id]

    asyncio.ensure_future(peer_pool.run())
    asyncio.ensure_future(connect_to_peers_loop(peer_pool, nodes))
    chain = chain_class(base_db)
    syncer: BaseHeaderChainSyncer = None
    if args.fast:
        syncer = FastChainSyncer(chain, chaindb, peer_pool)
    elif args.light:
        syncer = LightChainSyncer(chain, headerdb, peer_pool)
    else:
        syncer = RegularChainSyncer(chain, chaindb, peer_pool)
    syncer.logger.setLevel(log_level)
    syncer.min_peers_to_sync = 1

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

    async def mock_run_in_executor(self, callback, *args):  # type: ignore
        return callback(*args)

    if profile:
        BaseHeaderChainSyncer._run_in_executor = mock_run_in_executor  # type: ignore
        cProfile.run('_test()', 'stats')
        pstats.Stats('stats').strip_dirs().sort_stats('cumulative').print_stats(50)
    else:
        _test()


if __name__ == "__main__":
    _run_test(profile=True)
