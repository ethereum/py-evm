from typing import (
    Type,
)

from eth.abc import BlockAPI, BlockHeaderAPI, ConsensusAPI
from eth.consensus.pos import PosConsensus
from eth.constants import (
    POST_MERGE_DIFFICULTY,
    POST_MERGE_NONCE,
    POST_MERGE_OMMERS_HASH,
)
from eth.rlp.blocks import BaseBlock
from eth.vm.forks.gray_glacier import GrayGlacierVM
from eth.vm.state import BaseState
from eth_utils import (
    ValidationError,
)

from .blocks import ParisBlock
from .headers import (
    configure_paris_header,
    create_paris_header_from_parent,
)
from .state import ParisState


class ParisVM(GrayGlacierVM):
    # fork name
    fork = "paris"

    # classes
    block_class: Type[BaseBlock] = ParisBlock
    _state_class: Type[BaseState] = ParisState
    consensus_class: Type[ConsensusAPI] = PosConsensus

    # Methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_paris_header_from_parent()
    )
    configure_header = configure_paris_header

    @staticmethod
    def get_block_reward() -> int:
        return 0

    @classmethod
    def get_nephew_reward(cls) -> int:
        return 0

    def _assign_block_rewards(self, block: BlockAPI) -> None:
        # No block reward or uncles / uncle rewards in PoS
        pass

    @classmethod
    def validate_header(
        cls, header: BlockHeaderAPI, parent_header: BlockHeaderAPI
    ) -> None:
        super().validate_header(header, parent_header)

        difficulty, nonce, uncles_hash = (
            header.difficulty,
            header.nonce,
            header.uncles_hash,
        )

        if difficulty != POST_MERGE_DIFFICULTY:
            raise ValidationError(
                f"Difficulty must be {POST_MERGE_DIFFICULTY}, got {difficulty}."
            )
        if nonce != POST_MERGE_NONCE:
            raise ValidationError(
                f"Nonce must be {POST_MERGE_NONCE !r}, got {nonce !r}."
            )
        if uncles_hash != POST_MERGE_OMMERS_HASH:
            raise ValidationError(
                f"Uncles hash must be {POST_MERGE_OMMERS_HASH !r}, "
                f"got {uncles_hash !r}."
            )
