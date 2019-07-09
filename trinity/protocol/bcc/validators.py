from typing import (
    cast,
    Tuple,
    Union,
)

from eth_typing import (
    Hash32,
)

from eth_utils import (
    ValidationError,
    encode_hex,
)
from eth_utils.toolz import (
    sliding_window,
)

from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.typing import (
    Slot,
)

from trinity.protocol.common.validators import BaseValidator

from trinity.protocol.bcc.commands import (
    RequestMessage,
    ResponseMessage,
)


class BeaconBlocksValidator(BaseValidator[Tuple[BaseBeaconBlock, ...]]):

    def __init__(self, block_slot_or_hash: Union[Slot, Hash32], max_blocks: int) -> None:
        self.block_slot_or_hash = block_slot_or_hash
        self.max_blocks = max_blocks

    def validate_result(self, result: Tuple[BaseBeaconBlock, ...]) -> None:
        self._validate_first_block(result)
        self._validate_number(result)
        self._validate_sequence(result)

    @property
    def _is_numbered(self) -> bool:
        return isinstance(self.block_slot_or_hash, int)

    def _validate_first_block(self, blocks: Tuple[BaseBeaconBlock, ...]) -> None:
        """Validate that the first returned block (if any) is the one that we requested."""
        try:
            first_block = blocks[0]
        except IndexError:
            return

        if self._is_numbered:
            if first_block.slot != self.block_slot_or_hash:
                raise ValidationError(
                    f"Requested blocks starting with slot #{self.block_slot_or_hash} but first "
                    f"returned block is from slot #{first_block.slot}"
                )
        else:
            if first_block.signing_root != self.block_slot_or_hash:
                block_hash = cast(Hash32, self.block_slot_or_hash)
                raise ValidationError(
                    f"Requested blocks starting with hash {encode_hex(block_hash)} "
                    f"but first returned block has hash {encode_hex(first_block.signing_root)}"
                )

    def _validate_number(self, blocks: Tuple[BaseBeaconBlock, ...]) -> None:
        """Validate that no more than the maximum requested number of blocks is returned."""
        if len(blocks) > self.max_blocks:
            raise ValidationError(
                f"Requested up to {self.max_blocks} blocks but received {len(blocks)}"
            )

    def _validate_sequence(self, blocks: Tuple[BaseBeaconBlock, ...]) -> None:
        # workaround for https://github.com/pytoolz/cytoolz/issues/123#issuecomment-432905716
        if not blocks:
            return

        for parent, child in sliding_window(2, blocks):
            # check that the received blocks form a sequence of descendents connected by parent
            # hashes, starting with the oldest ancestor
            if child.parent_root != parent.signing_root:
                raise ValidationError(
                    "Returned blocks are not a connected branch"
                )


def match_payload_request_id(request: RequestMessage, response: ResponseMessage) -> None:
    if request['request_id'] != response['request_id']:
        raise ValidationError("Request `id` does not match")
