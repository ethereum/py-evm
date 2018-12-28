from typing import (
    Iterable,
    Tuple,
)
from cytoolz import (
    pipe
)

from eth._utils import bls
from eth._utils.bitfield import (
    set_voted,
)
from eth.beacon.enums import SignatureDomain
from eth.beacon.typing import (
    BLSPubkey,
    BLSSignatureBytes,
    BLSSignatureIntegers,
    Bitfield,
    CommitteeIndex,
)


def verify_votes(
    message: bytes,
    votes: Iterable[Tuple[CommitteeIndex, BLSSignatureBytes, BLSPubkey]],
    domain: SignatureDomain
) -> Tuple[Tuple[BLSSignatureBytes, ...], Tuple[CommitteeIndex, ...]]:
    """
    Verify the given votes.

    vote: (committee_index, sig, public_key)
    """
    sigs_with_committe_info = tuple(
        (sig, committee_index)
        for (committee_index, sig, public_key)
        in votes
        if bls.verify(message, public_key, sig, domain)
    )
    try:
        sigs, committee_indices = zip(*sigs_with_committe_info)
    except ValueError:
        sigs = tuple()
        committee_indices = tuple()

    return sigs, committee_indices


def aggregate_votes(
    bitfield: Bitfield,
    sigs: Iterable[BLSSignatureBytes],
    voting_sigs: Iterable[BLSSignatureBytes],
    voting_committee_indices: Iterable[CommitteeIndex]
) -> Tuple[Bitfield, BLSSignatureIntegers]:
    """
    Aggregate the votes.
    """
    # Update the bitfield and append the signatures
    sigs = tuple(sigs) + tuple(voting_sigs)
    bitfield = pipe(
        bitfield,
        *(
            set_voted(index=committee_index)
            for committee_index in voting_committee_indices
        )
    )

    return bitfield, bls.aggregate_signatures(sigs)
