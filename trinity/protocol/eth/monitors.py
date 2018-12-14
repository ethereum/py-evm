from trinity.protocol.common.monitors import BaseChainTipMonitor
from trinity.protocol.eth import commands


class ETHChainTipMonitor(BaseChainTipMonitor):
    subscription_msg_types = frozenset({commands.NewBlock})
