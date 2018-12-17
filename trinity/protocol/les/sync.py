from trinity.protocol.les.monitors import LightChainTipMonitor
from trinity.protocol.les.peer import LESPeer
from trinity.sync.common.headers import BaseHeaderChainSyncer


class LightHeaderChainSyncer(BaseHeaderChainSyncer[LESPeer]):
    tip_monitor_class = LightChainTipMonitor
