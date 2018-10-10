from eth.beacon.types.blocks import BaseBeaconBlock


class SerenityBeaconBlock(BaseBeaconBlock):
    @classmethod
    def from_block(cls, block):
        return cls(
            parent_hash=block.parent_hash,
            slot_number=block.slot_number,
            randao_reveal=block.randao_reveal,
            attestations=block.attestations,
            pow_chain_ref=block.pow_chain_ref,
            active_state_root=block.active_state_root,
            crystallized_state_root=block.crystallized_state_root,
        )
