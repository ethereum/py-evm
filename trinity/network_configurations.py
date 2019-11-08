from typing import (
    NamedTuple,
    Tuple,
)

from p2p.constants import (
    MAINNET_BOOTNODES,
    ROPSTEN_BOOTNODES,
)
from trinity.constants import (
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID
)


class Eth1NetworkConfiguration(NamedTuple):

    network_id: int
    chain_name: str
    data_dir_name: str
    eip1085_filename: str
    bootnodes: Tuple[str, ...]


PRECONFIGURED_NETWORKS = {
    MAINNET_NETWORK_ID: Eth1NetworkConfiguration(
        MAINNET_NETWORK_ID,
        'MainnetChain',
        'mainnet',
        'mainnet.json',
        MAINNET_BOOTNODES
    ),
    ROPSTEN_NETWORK_ID: Eth1NetworkConfiguration(
        ROPSTEN_NETWORK_ID,
        'RopstenChain',
        'ropsten',
        'ropsten.json',
        ROPSTEN_BOOTNODES
    ),
}
