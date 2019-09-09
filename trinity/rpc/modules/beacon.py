from typing import Any, Dict

from eth_utils import (
    encode_hex,
)

from eth2.beacon.types.blocks import BeaconBlock
from trinity.rpc.modules import BeaconChainRPCModule


class Beacon(BeaconChainRPCModule):

    async def currentSlot(self) -> str:
        return hex(666)

    async def head(self) -> Dict[Any, Any]:
        block = await self.chain.coro_get_canonical_head(BeaconBlock)
        return dict(
            slot=block.slot,
            block_root=encode_hex(block.signing_root),
            state_root=encode_hex(block.state_root),
        )
