from typing import Any, Dict

from eth_utils import (
    decode_hex,
    encode_hex,
)
from ssz.tools import (
    to_formatted_dict,
)

from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.typing import SigningRoot, Slot
from trinity.rpc.format import (
    format_params,
    to_int_if_hex,
)
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

    #
    # Debug
    #
    async def getFinalizedHead(self) -> Dict[Any, Any]:
        """
        Return finalized head block.
        """
        block = await self.chain.coro_get_finalized_head(BeaconBlock)
        return to_formatted_dict(block, sedes=BeaconBlock)

    @format_params(to_int_if_hex)
    async def getCanonicalBlockBySlot(self, slot: Slot) -> Dict[Any, Any]:
        """
        Return the canonical block of the given slot.
        """
        block = await self.chain.coro_get_canonical_block_by_slot(slot, BeaconBlock)
        return to_formatted_dict(block, sedes=BeaconBlock)

    @format_params(decode_hex)
    async def getBlockByRoot(self, root: SigningRoot) -> Dict[Any, Any]:
        """
        Return the block of given root.
        """
        block = await self.chain.coro_get_block_by_root(root, BeaconBlock)
        return to_formatted_dict(block, sedes=BeaconBlock)

    async def getGenesisBlockRoot(self) -> str:
        """
        Return genesis ``SigningRoot`` in hex string.
        """
        block_root = await self.chain.coro_get_genesis_block_root()
        return encode_hex(block_root)
