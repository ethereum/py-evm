from typing import (
    Iterable
)

from eth_typing import (
    Hash32,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth.beacon.types.attestation_records import AttestationRecord  # noqa: F401
from eth.beacon.types.blocks import BaseBeaconBlock


class SerenityBeaconBlock(BaseBeaconBlock):
    @classmethod
    def from_parent(cls,
                    parent_block: BaseBeaconBlock,
                    slot_number: int=None,
                    randao_reveal: Hash32=None,
                    attestations: Iterable['AttestationRecord']=None,
                    pow_chain_ref: Hash32=None,
                    active_state_root: Hash32=ZERO_HASH32,
                    crystallized_state_root: Hash32=ZERO_HASH32) -> BaseBeaconBlock:
        """
        Initialize a new block with the `parent` block as the block's
        parent hash.
        """
        if slot_number is None:
            slot_number = parent_block.slot_number + 1
        if randao_reveal is None:
            randao_reveal = parent_block.randao_reveal
        if attestations is None:
            attestations = ()
        if pow_chain_ref is None:
            pow_chain_ref = parent_block.pow_chain_ref

        block_params = {
            'parent_hash': parent_block.hash,
            'slot_number': slot_number,
            'randao_reveal': randao_reveal,
            'attestations': attestations,
            'pow_chain_ref': pow_chain_ref,
            'active_state_root': active_state_root,
            'crystallized_state_root': crystallized_state_root,
        }

        block = cls(**block_params)
        return block


def create_serenity_block_from_parent(parent_block, **block_params):
    block = SerenityBeaconBlock.from_parent(parent_block=parent_block, **block_params)

    return block
