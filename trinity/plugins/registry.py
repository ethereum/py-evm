import pkg_resources
from typing import (
    Tuple,
    Type,
)

from trinity.extensibility import (
    BasePlugin,
)
from trinity.plugins.builtin.attach.plugin import (
    DbShellPlugin,
    AttachPlugin,
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
from trinity.plugins.builtin.network_db.plugin import (
    NetworkDBPlugin,
)
from trinity.plugins.builtin.peer_discovery.plugin import (
    PeerDiscoveryPlugin,
)
from trinity.plugins.builtin.syncer.plugin import (
    SyncerPlugin,
)
from trinity.plugins.eth2.network_generator.plugin import NetworkGeneratorPlugin
from trinity.plugins.eth2.beacon.plugin import BeaconNodePlugin
from trinity.plugins.builtin.tx_pool.plugin import (
    TxPlugin,
)
from trinity.plugins.builtin.light_peer_chain_bridge.plugin import (
    LightPeerChainBridgePlugin
)


BASE_PLUGINS: Tuple[Type[BasePlugin], ...] = (
    AttachPlugin,
    NetworkGeneratorPlugin,
    FixUncleanShutdownPlugin,
    JsonRpcServerPlugin,
    NetworkDBPlugin,
    PeerDiscoveryPlugin,
    BeaconNodePlugin,
)


ETH1_NODE_PLUGINS: Tuple[Type[BasePlugin], ...] = (
    DbShellPlugin,
    EthstatsPlugin,
    LightPeerChainBridgePlugin,
    SyncerPlugin,
    TxPlugin,
)


def discover_plugins() -> Tuple[Type[BasePlugin], ...]:
    # Plugins need to define entrypoints at 'trinity.plugins' to automatically get loaded
    # https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata

    return tuple(
        entry_point.load() for entry_point in pkg_resources.iter_entry_points('trinity.plugins')
    )
