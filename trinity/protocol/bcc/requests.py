from typing import (
    Union,
)

from eth_typing import (
    Hash32,
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
                 block_slot_or_hash: Union[int, Hash32],
                 max_blocks: int,
                 request_id: int) -> None:
        self.command_payload = GetBeaconBlocksMessage(
            request_id=request_id,
            block_slot_or_hash=block_slot_or_hash,
            max_blocks=max_blocks,
        )
