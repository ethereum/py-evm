from trinity.protocol.eth.monitors import ETHChainTipMonitor
from trinity.protocol.eth.peer import ETHPeer
from trinity.sync.common.headers import BaseHeaderChainSyncer


class ETHHeaderChainSyncer(BaseHeaderChainSyncer[ETHPeer]):
    tip_monitor_class = ETHChainTipMonitor
