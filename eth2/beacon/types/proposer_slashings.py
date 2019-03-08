import ssz
from ssz.sedes import (
    uint64,
)

from .proposal import Proposal
from eth2.beacon.typing import (
    ValidatorIndex,
)


class ProposerSlashing(ssz.Serializable):

    fields = [
        # Proposer index
        ('proposer_index', uint64),
        # First proposal
        ('proposal_1', Proposal),
        # Second proposal
        ('proposal_2', Proposal),
    ]

    def __init__(self,
                 proposer_index: ValidatorIndex,
                 proposal_1: Proposal,
                 proposal_2: Proposal) -> None:
        super().__init__(
            proposer_index=proposer_index,
            proposal_1=proposal_1,
            proposal_2=proposal_2,
        )
