from typing import (
    Any
)

from eth_utils import (
    encode_hex,
)
from lahja import (
    BroadcastConfig,
)

from eth.chains.base import (
    BaseChain
)
from eth.tools._utils.normalization import (
    normalize_block,
    normalize_blockchain_fixtures,
)
from eth.tools.fixtures import (
    apply_fixture_block_to_chain,
    new_chain_from_fixture,
)

from trinity.rpc.format import (
    format_params,
)
from trinity.rpc.modules import (
    ChainReplacementEvent,
    Eth1ChainRPCModule,
)


class EVM(Eth1ChainRPCModule):

    @format_params(normalize_blockchain_fixtures)
    async def resetToGenesisFixture(self, chain_info: Any) -> BaseChain:
        """
        This method is a special case. It returns a new chain object
        which is then replaced inside :class:`~trinity.rpc.main.RPCServer`
        for all future calls.
        """
        chain = new_chain_from_fixture(chain_info, type(self.chain))

        await self.event_bus.broadcast(
            ChainReplacementEvent(chain),
            BroadcastConfig(internal=True)
        )

        return chain

    @format_params(normalize_block)
    async def applyBlockFixture(self, block_info: Any) -> str:
        """
        This method is a special case. It returns a new chain object
        which is then replaced inside :class:`~trinity.rpc.main.RPCServer`
        for all future calls.
        """
        _, _, rlp_encoded = apply_fixture_block_to_chain(block_info, self.chain)
        return encode_hex(rlp_encoded)
