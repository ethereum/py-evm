import ssz
from ssz.sedes import (
    bytes_sedes,
    uint64,
)

from .proposal import Proposal
from eth2.beacon.typing import (
    BLSSignature,
    ValidatorIndex,
)
from eth2.beacon.constants import EMPTY_SIGNATURE


class ProposerSlashing(ssz.Serializable):

    fields = [
        # Proposer index
        ('proposer_index', uint64),
        # First proposal data
        ('proposal_1', Proposal),
        # First proposal signature
        ('proposal_signature_1', bytes_sedes),
        # Second proposal data
        ('proposal_2', Proposal),
        # Second proposal signature
        ('proposal_signature_2', bytes_sedes),
    ]

    def __init__(self,
                 proposer_index: ValidatorIndex,
                 proposal_1: Proposal,
                 proposal_2: Proposal,
                 # default arguments follow non-default arguments
                 proposal_signature_1: BLSSignature = EMPTY_SIGNATURE,
                 proposal_signature_2: BLSSignature = EMPTY_SIGNATURE) -> None:
        super().__init__(
            proposer_index=proposer_index,
            proposal_1=proposal_1,
            proposal_2=proposal_2,
            proposal_signature_1=proposal_signature_1,
            proposal_signature_2=proposal_signature_2,
        )
