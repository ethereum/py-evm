from eth import MainnetChain, RopstenChain
from eth.chains.base import (
    MiningChain,
)
from eth.vm.forks.byzantium import ByzantiumVM
from eth.vm.forks.petersburg import PetersburgVM

from trinity.chains.coro import AsyncChainMixin
from trinity.chains.full import FullChain


class AsyncRopstenChain(AsyncChainMixin, RopstenChain):
    pass


class AsyncMainnetChain(AsyncChainMixin, MainnetChain):
    pass


class AsyncMiningChain(AsyncChainMixin, MiningChain):
    pass


class LatestTestChain(FullChain):
    """
    A test chain that uses the most recent mainnet VM from block 0.
    That means the VM will explicitly change when a new network upgrade is locked in.
    """
    vm_configuration = ((0, PetersburgVM),)
    network_id = 999


class ByzantiumTestChain(FullChain):
    vm_configuration = ((0, ByzantiumVM),)
    network_id = 999
