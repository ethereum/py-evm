from eth import MainnetChain, RopstenChain
from eth.chains.base import (
    MiningChain,
)
from eth.constants import GENESIS_BLOCK_NUMBER
from eth.vm.forks.byzantium import ByzantiumVM
from eth.vm.forks.istanbul import IstanbulVM

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
    vm_configuration = ((GENESIS_BLOCK_NUMBER, IstanbulVM),)
    network_id = 999


class ByzantiumTestChain(FullChain):
    vm_configuration = ((GENESIS_BLOCK_NUMBER, ByzantiumVM),)
    network_id = 999
