from typing import (
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

from eth.beacon.types.blocks import BaseBeaconBlock

from trinity.protocol.common.validators import BaseValidator

from trinity.protocol.bcc.commands import (
    RequestMessage,
    ResponseMessage,
)


class BeaconBlocksValidator(BaseValidator[Tuple[BaseBeaconBlock, ...]]):

    def __init__(self, block_slot_or_hash: Union[int, Hash32], max_blocks: int) -> None:
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
            if first_block.hash != self.block_slot_or_hash:
                raise ValidationError(
                    f"Requested blocks starting with hash {encode_hex(self.block_slot_or_hash)} "
                    f"but first returned block has hash {encode_hex(first_block.hash)}"
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
            if child.parent_root != parent.hash:
                raise ValidationError(
                    "Returned blocks are not a connected branch"
                )
            # check that the blocks are ordered by slot and no slot is missing
            if child.slot != parent.slot + 1:
                raise ValidationError(
                    f"Slot of returned block {child} is not the successor of its parent"
                )


def match_payload_request_id(request: RequestMessage, response: ResponseMessage) -> None:
    if request['request_id'] != response['request_id']:
        raise ValidationError("Request `id` does not match")
