import rlp
from rlp.sedes import (
    CountableList,
)
from eth.rlp.sedes import (
    uint24,
    uint384,
)
from .proposal_signed_data import ProposalSignedData
from eth.beacon.typing import (
    BLSSignature,
    ValidatorIndex,
)
from eth.beacon.constants import EMPTY_SIGNATURE


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
                 proposer_index: ValidatorIndex,
                 proposal_data_1: ProposalSignedData,
                 proposal_data_2: ProposalSignedData,
                 # default arguments follow non-default arguments
                 proposal_signature_1: BLSSignature = EMPTY_SIGNATURE,
                 proposal_signature_2: BLSSignature = EMPTY_SIGNATURE) -> None:
        super().__init__(
            proposer_index=proposer_index,
            proposal_data_1=proposal_data_1,
            proposal_data_2=proposal_data_2,
            proposal_signature_1=proposal_signature_1,
            proposal_signature_2=proposal_signature_2,
        )
