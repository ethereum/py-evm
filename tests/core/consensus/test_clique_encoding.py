import pytest

from eth.consensus.clique.datatypes import (
    Snapshot,
    Tally,
    Vote,
    VoteAction,
)
from eth.consensus.clique.encoding import (
    decode_address_tally_pair,
    decode_snapshot,
    decode_tally,
    decode_vote,
    encode_address_tally_pair,
    encode_snapshot,
    encode_tally,
    encode_vote,
)
from eth.constants import (
    GENESIS_PARENT_HASH,
    ZERO_ADDRESS,
)

SOME_ADDRESS = b"\x85\x82\xa2\x89V\xb9%\x93M\x03\xdd\xb4Xu\xe1\x8e\x85\x93\x12\xc1"

DUMMY_VOTE_1 = Vote(
    signer=SOME_ADDRESS, block_number=666, subject=ZERO_ADDRESS, action=VoteAction.KICK
)

DUMMY_VOTE_2 = Vote(
    signer=ZERO_ADDRESS, block_number=500, subject=SOME_ADDRESS, action=VoteAction.KICK
)

TRUMP_TALLY = Tally(action=VoteAction.KICK, votes=666)
YANG_TALLY = Tally(action=VoteAction.NOMINATE, votes=1000)

SNAPSHOT_1 = Snapshot(
    signers=frozenset({ZERO_ADDRESS, SOME_ADDRESS}),
    block_hash=GENESIS_PARENT_HASH,
    votes=frozenset({DUMMY_VOTE_1, DUMMY_VOTE_2}),
    tallies={ZERO_ADDRESS: TRUMP_TALLY, SOME_ADDRESS: YANG_TALLY},
)


ADDRESS_TALLY_PAIRS = list(SNAPSHOT_1.tallies.items())


@pytest.mark.parametrize(
    "val, meant_to_be, encode_fn, decode_fn",
    (
        (
            ADDRESS_TALLY_PAIRS[0],
            tuple,
            encode_address_tally_pair,
            decode_address_tally_pair,
        ),
        (DUMMY_VOTE_1, Vote, encode_vote, decode_vote),
        (DUMMY_VOTE_2, Vote, encode_vote, decode_vote),
        (SNAPSHOT_1, Snapshot, encode_snapshot, decode_snapshot),
        (TRUMP_TALLY, Tally, encode_tally, decode_tally),
        (YANG_TALLY, Tally, encode_tally, decode_tally),
    ),
)
def test_encoding_decoding(val, meant_to_be, encode_fn, decode_fn):
    assert type(val) is meant_to_be
    binary = encode_fn(val)
    assert type(binary) is bytes
    revived = decode_fn(binary)
    assert revived == val
