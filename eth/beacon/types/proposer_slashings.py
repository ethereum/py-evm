from typing import Sequence
import rlp
from rlp.sedes import (
    CountableList,
)
from eth.rlp.sedes import (
    uint24,
    uint384,
)
from .proposal_signed_data import ProposalSignedData


class ProposerSlashing(rlp.Serializable):
    fields = [
        # Proposer index
        ('proposer_index', uint24),
        # First proposal data
        ('proposal_data_1', ProposalSignedData),
        # First proposal signature
        ('proposal_signature_1', CountableList(uint384)),
        # Second proposal data
        ('proposal_data_2', ProposalSignedData),
        # Second proposal signature
        ('proposal_signature_2', CountableList(uint384)),
    ]

    def __init__(self,
                 proposer_index: int,
                 proposal_data_1: ProposalSignedData,
                 proposal_signature_1: Sequence[int],
                 proposal_data_2: ProposalSignedData,
                 proposal_signature_2: Sequence[int]) -> None:
        super().__init__(
            proposer_index,
            proposal_data_1,
            proposal_signature_1,
            proposal_data_2,
            proposal_signature_2,
        )
