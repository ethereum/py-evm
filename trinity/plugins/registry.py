from trinity.plugins.builtin.tx_pool.plugin import (
    TxPlugin
)


# This is our poor mans central plugin registry for now. In the future,
# we'll be able to load plugins from some path and control via Trinity
# config file which plugin is enabled or not

ENABLED_PLUGINS = [
    TxPlugin()
]
