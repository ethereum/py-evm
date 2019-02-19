from typing import (
    Union,
)

from eth_typing import (
    Hash32,
)

from eth2.beacon.typing import (
    Slot,
)

from p2p.protocol import (
    BaseRequest,
)

from trinity.protocol.bcc.commands import (
    GetBeaconBlocks,
    GetBeaconBlocksMessage,
    BeaconBlocks,
)


class GetBeaconBlocksRequest(BaseRequest[GetBeaconBlocksMessage]):
    cmd_type = GetBeaconBlocks
    response_type = BeaconBlocks

    def __init__(self,
                 block_slot_or_root: Union[Slot, Hash32],
                 max_blocks: int,
                 request_id: int) -> None:
        self.command_payload = GetBeaconBlocksMessage(
            request_id=request_id,
            block_slot_or_root=block_slot_or_root,
            max_blocks=max_blocks,
        )
