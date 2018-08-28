import pkg_resources

from trinity.plugins.builtin.attach.plugin import (
    AttachPlugin
)
from trinity.plugins.builtin.fix_unclean_shutdown.plugin import (
    FixUncleanShutdownPlugin
)
from trinity.plugins.builtin.json_rpc.plugin import (
    JsonRpcServerPlugin,
)
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


# This is our poor mans central plugin registry for now. In the future,
# we'll be able to load plugins from some path and control via Trinity
# config file which plugin is enabled or not

ENABLED_PLUGINS = [
    AttachPlugin() if is_ipython_available() else AttachPlugin(use_ipython=False),
    FixUncleanShutdownPlugin(),
    JsonRpcServerPlugin(),
    LightPeerChainBridgePlugin(),
    TxPlugin(),
]
