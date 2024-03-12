from typing import (
    Tuple,
)

from eth_typing import (
    Address,
)
import rlp

from eth.consensus.clique.datatypes import (
    Snapshot,
    Tally,
    Vote,
    VoteAction,
)
from eth.rlp.sedes import (
    uint256,
)

ADDRESS_TALLY_SEDES = rlp.sedes.List((rlp.sedes.binary, rlp.sedes.binary))
VOTE_SEDES = rlp.sedes.List(
    (
        rlp.sedes.binary,
        uint256,
        rlp.sedes.binary,
        rlp.sedes.binary,
    )
)
SNAPSHOT_SEDES = rlp.sedes.List(
    (
        rlp.sedes.binary,
        rlp.sedes.CountableList(rlp.sedes.binary),
        rlp.sedes.CountableList(rlp.sedes.binary),
        rlp.sedes.CountableList(rlp.sedes.binary),
    )
)
TALLY_SEDES = rlp.sedes.List((rlp.sedes.binary, uint256))


def encode_address_tally_pair(pair: Tuple[Address, Tally]) -> bytes:
    return rlp.encode(
        [pair[0], encode_tally(pair[1])],
        sedes=ADDRESS_TALLY_SEDES,
    )


def decode_address_tally_pair(pair: bytes) -> Tuple[Address, Tally]:
    (
        address,
        tally_bytes,
    ) = rlp.decode(
        pair,
        sedes=ADDRESS_TALLY_SEDES,
    )

    tally = decode_tally(tally_bytes)

    return address, tally


def encode_vote(vote: Vote) -> bytes:
    return rlp.encode(
        [
            vote.signer,
            vote.block_number,
            vote.subject,
            vote.action.value,
        ],
        sedes=VOTE_SEDES,
    )


def decode_vote(vote: bytes) -> Vote:
    signer, block_number, subject, action = rlp.decode(
        vote,
        sedes=VOTE_SEDES,
    )
    return Vote(
        signer=signer,
        block_number=block_number,
        subject=subject,
        action=VoteAction.NOMINATE
        if action == VoteAction.NOMINATE.value
        else VoteAction.KICK,
    )


def encode_snapshot(snapshot: Snapshot) -> bytes:
    return rlp.encode(
        [
            snapshot.block_hash,
            list(snapshot.signers),
            [encode_vote(vote) for vote in snapshot.votes],
            [
                encode_address_tally_pair((address, tally))
                for address, tally in snapshot.tallies.items()
            ],
        ],
        sedes=SNAPSHOT_SEDES,
    )


def decode_snapshot(snapshot: bytes) -> Snapshot:
    block_hash, signers, votes_rlp, tallies_rlp = rlp.decode(
        snapshot,
        sedes=SNAPSHOT_SEDES,
    )

    votes = [decode_vote(vote) for vote in votes_rlp]
    tallies = dict(decode_address_tally_pair(pair) for pair in tallies_rlp)

    return Snapshot(
        signers=frozenset(signers),
        block_hash=block_hash,
        votes=frozenset(votes),
        tallies=tallies,
    )


def encode_tally(tally: Tally) -> bytes:
    return rlp.encode(
        [tally.action.value, tally.votes],
        sedes=TALLY_SEDES,
    )


def decode_tally(tally: bytes) -> Tally:
    action_binary, votes = rlp.decode(
        tally,
        sedes=TALLY_SEDES,
    )

    return Tally(action=VoteAction(action_binary), votes=votes)
