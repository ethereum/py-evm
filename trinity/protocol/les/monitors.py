from trinity.protocol.common.monitors import BaseChainTipMonitor
from trinity.protocol.les import commands


class LightChainTipMonitor(BaseChainTipMonitor):
    subscription_msg_types = {commands.Announce}
