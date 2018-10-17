from typing import (
    Iterable,
    Tuple,
)
from cytoolz import (
    pipe
)

from eth_typing import (
    Hash32,
)

from eth.utils import bls
from eth.utils.bitfield import (
    set_voted,
)
from eth.utils.blake import blake


def create_signing_message(slot: int,
                           parent_hashes: Iterable[Hash32],
                           shard_id: int,
                           shard_block_hash: Hash32,
                           justified_slot: int) -> bytes:
    """
    Return the signining message for attesting.
    """
    # TODO: Will be updated with SSZ encoded attestation.
    return blake(
        slot.to_bytes(8, byteorder='big') +
        b''.join(parent_hashes) +
        shard_id.to_bytes(2, byteorder='big') +
        shard_block_hash +
        justified_slot.to_bytes(8, 'big')
    )


def verify_votes(
        message: bytes,
        votes: Iterable[Tuple[int, bytes, int]]) -> Tuple[Tuple[bytes, ...], Tuple[int, ...]]:
    """
    Verify the given votes.

    vote: (committee_index, sig, public_key)
    """
    sigs_with_committe_info = tuple(
        (sig, committee_index)
        for (committee_index, sig, public_key)
        in votes
        if bls.verify(message, public_key, sig)
    )
    try:
        sigs, committee_indices = zip(*sigs_with_committe_info)
    except ValueError:
        sigs = tuple()
        committee_indices = tuple()

    return sigs, committee_indices


def aggregate_votes(bitfield: bytes,
                    sigs: Iterable[bytes],
                    voting_sigs: Iterable[bytes],
                    voting_committee_indices: Iterable[int]) -> Tuple[bytes, Tuple[int, int]]:
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

    return bitfield, bls.aggregate_sigs(sigs)
