from eth.abc import (
    BlockAndMetaWitness,
    BlockAPI,
    VirtualMachineAPI,
)
from eth.consensus import (
    pow,
)


class POWMiningMixin(VirtualMachineAPI):
    """
    A VM that does POW mining as well. Should be used only in tests, when we
    need to programatically populate a ChainDB.
    """

    def finalize_block(self, block: BlockAPI) -> BlockAndMetaWitness:
        # type ignored because as a mixin, we expect to only use this with another
        # class that properly implements finalize_block
        block_result = super().finalize_block(block)  # type: ignore[safe-super]
        block = block_result.block

        nonce, mix_hash = pow.mine_pow_nonce(
            block.number, block.header.mining_hash, block.header.difficulty
        )

        mined_block = block.copy(
            header=block.header.copy(nonce=nonce, mix_hash=mix_hash)
        )

        return BlockAndMetaWitness(mined_block, block_result.meta_witness)
