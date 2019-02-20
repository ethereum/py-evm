from typing import (
    Tuple,
    Union,
)

from eth_typing import (
    Hash32,
)

from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)

from eth2.beacon.typing import (
    Slot,
)

from trinity._utils.les import (
    gen_request_id,
)

from trinity.protocol.common.exchanges import BaseExchange
from trinity.protocol.bcc.normalizers import BeaconBlocksNormalizer
from trinity.protocol.bcc.requests import GetBeaconBlocksRequest
from trinity.protocol.bcc.trackers import GetBeaconBlocksTracker
from trinity.protocol.bcc.validators import (
    BeaconBlocksValidator,
    match_payload_request_id,
)
from trinity.protocol.bcc.commands import (
    GetBeaconBlocksMessage,
    BeaconBlocksMessage,
)


class BeaconBlocksExchange(BaseExchange[GetBeaconBlocksMessage,
                                        BeaconBlocksMessage,
                                        Tuple[BaseBeaconBlock, ...]]):
    _normalizer = BeaconBlocksNormalizer()
    request_class = GetBeaconBlocksRequest
    tracker_class = GetBeaconBlocksTracker

    async def __call__(self,  # type: ignore
                       block_slot_or_hash: Union[Slot, Hash32],
                       max_headers: int = None,
                       timeout: float = None) -> Tuple[BaseBeaconBlock, ...]:

        validator = BeaconBlocksValidator(block_slot_or_hash, max_headers)

        request = self.request_class(block_slot_or_hash, max_headers, gen_request_id())

        return await self.get_result(
            request,
            self._normalizer,
            validator,
            match_payload_request_id,
            timeout,
        )
