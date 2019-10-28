try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")

from eth_utils import to_bytes

from eth.chains.mainnet import MAINNET_VM_CONFIGURATION

from trinity.protocol.common.context import ChainContext

from .db import AsyncHeaderDBFactory

MAINNET_GENESIS_HASH = to_bytes(hexstr='0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3')  # noqa: E501


class ChainContextFactory(factory.Factory):
    class Meta:
        model = ChainContext

    network_id = 1
    client_version_string = 'test'
    headerdb = factory.SubFactory(AsyncHeaderDBFactory)
    vm_configuration = ((0, MAINNET_VM_CONFIGURATION[-1][1]),)
    listen_port = 30303
    p2p_version = 5
