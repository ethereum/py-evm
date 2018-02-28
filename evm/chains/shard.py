from evm.exceptions import (
    ValidationError,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.rlp import (
    ensure_imported_block_unchanged,
)


from .base import (
    BaseChain,
)


class Shard(BaseChain):
    def apply_block_with_witness(self, block, witness, perform_validation=True):
        """
        Import a complete block with witness.
        """
        if block.number > self.header.block_number:
            raise ValidationError(
                "Attempt to import block #{0}.  Cannot import block with number "
                "greater than current block #{1}.".format(
                    block.number,
                    self.header.block_number,
                )
            )

        parent_chain = self.get_chain_at_block_parent(block)
        imported_block = parent_chain.get_vm().apply_block_with_witness(block, witness)

        # Validate the imported block.
        if perform_validation:
            ensure_imported_block_unchanged(imported_block, block)
            self.validate_block(imported_block)

        self.chaindb.persist_block_to_db(imported_block)
        self.header = self.create_header_from_parent(self.get_canonical_head())
        self.logger.debug(
            'IMPORTED_BLOCK: number %s | hash %s',
            imported_block.number,
            encode_hex(imported_block.hash),
        )
        return imported_block
