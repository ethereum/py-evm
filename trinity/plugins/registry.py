import pkg_resources
from typing import (
    Tuple,
)

from trinity.extensibility import (
    BasePlugin,
)
from trinity.plugins.builtin.attach.plugin import (
    DbShellPlugin,
    AttachPlugin,
)
from trinity.plugins.builtin.blacklist.plugin import (
    BlacklistPlugin,
)
from trinity.plugins.builtin.ethstats.plugin import (
    EthstatsPlugin,
)
from trinity.plugins.builtin.fix_unclean_shutdown.plugin import (
    FixUncleanShutdownPlugin
)
from trinity.plugins.builtin.json_rpc.plugin import (
    JsonRpcServerPlugin,
)
from trinity.plugins.builtin.peer_discovery.plugin import (
    PeerDiscoveryPlugin,
)
from trinity.plugins.builtin.syncer.plugin import (
    FastThenFullSyncStrategy,
    FullSyncStrategy,
    LightSyncStrategy,
    NoopSyncStrategy,
    SyncerPlugin,
)
from trinity.plugins.eth2.beacon.plugin import BeaconNodePlugin
from trinity.plugins.builtin.tx_pool.plugin import (
    TxPlugin,
)
from trinity.plugins.builtin.light_peer_chain_bridge.plugin import (
    LightPeerChainBridgePlugin
)


def is_ipython_available() -> bool:
    try:
        pkg_resources.get_distribution('IPython')
    except pkg_resources.DistributionNotFound:
        return False
    else:
        return True


BASE_PLUGINS: Tuple[BasePlugin, ...] = (
    AttachPlugin(use_ipython=is_ipython_available()),
    FixUncleanShutdownPlugin(),
    JsonRpcServerPlugin(),
    PeerDiscoveryPlugin(),
    BeaconNodePlugin(),
)


ETH1_NODE_PLUGINS: Tuple[BasePlugin, ...] = (
    BlacklistPlugin(),
    DbShellPlugin(use_ipython=is_ipython_available()),
    EthstatsPlugin(),
    LightPeerChainBridgePlugin(),
    SyncerPlugin((
        FastThenFullSyncStrategy(),
        FullSyncStrategy(),
        LightSyncStrategy(),
        NoopSyncStrategy(),
    ), FastThenFullSyncStrategy),
    TxPlugin(),
)


def discover_plugins() -> Tuple[BasePlugin, ...]:
    # Plugins need to define entrypoints at 'trinity.plugins' to automatically get loaded
    # https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata

    return tuple(
        entry_point.load()() for entry_point in pkg_resources.iter_entry_points('trinity.plugins')
    )
