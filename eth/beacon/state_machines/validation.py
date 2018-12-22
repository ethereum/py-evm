from eth_utils import (
    ValidationError,
)

from eth.beacon.enums import (
    SignatureDomain,
)
from eth.beacon.helpers import (
    get_beacon_proposer_index,
    get_domain,
)
from eth.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth.beacon.types.proposal_signed_data import (
    ProposalSignedData,
)
from eth.beacon.types.states import (
    BeaconState,
)

from eth._utils.bls import (
    verify,
)


def validate_proposer_signature(state: BeaconState,
                                block: BaseBeaconBlock,
                                beacon_chain_shard_number: int,
                                epoch_length: int) -> None:
    block_without_signature_root = BaseBeaconBlock.create_block_without_signature_root(block).root

    proposal_root = ProposalSignedData(
        state.slot,
        beacon_chain_shard_number,
        block_without_signature_root
    ).root

    # Get the public key of proposer
    beacon_proposer_index = get_beacon_proposer_index(state, state.slot, epoch_length)
    proposer_pubkey = state.validator_registry[beacon_proposer_index].pubkey

    if not verify(
            pubkey=proposer_pubkey,
            message=proposal_root,
            signature=block.signature,
            domain=get_domain(state.fork_data, state.slot, SignatureDomain.DOMAIN_PROPOSAL)):
        raise ValidationError("Invalid Proposer Signature on block")
