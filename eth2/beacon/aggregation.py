from typing import (
    Iterable,
    Tuple,
)
from cytoolz import (
    pipe
)

from eth2._utils import bls
from eth2._utils.bitfield import (
    set_voted,
)
from eth2.beacon.enums import SignatureDomain
from eth2.beacon.typing import (
    BLSPubkey,
    BLSSignature,
    Bitfield,
    CommitteeIndex,
)


def verify_votes(
    message: bytes,
    votes: Iterable[Tuple[CommitteeIndex, BLSSignature, BLSPubkey]],
    domain: SignatureDomain
) -> Tuple[Tuple[BLSSignature, ...], Tuple[CommitteeIndex, ...]]:
    """
    Verify the given votes.

    vote: (committee_index, sig, public_key)
    """
    sigs_with_committee_info = tuple(
        (sig, committee_index)
        for (committee_index, sig, public_key)
        in votes
        if bls.verify(message, public_key, sig, domain)
    )
    try:
        sigs, committee_indices = zip(*sigs_with_committee_info)
    except ValueError:
        sigs = tuple()
        committee_indices = tuple()

    return sigs, committee_indices


def aggregate_votes(
    bitfield: Bitfield,
    sigs: Iterable[BLSSignature],
    voting_sigs: Iterable[BLSSignature],
    voting_committee_indices: Iterable[CommitteeIndex]
) -> Tuple[Bitfield, BLSSignature]:
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
