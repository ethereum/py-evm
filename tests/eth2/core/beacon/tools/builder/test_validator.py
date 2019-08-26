from eth_utils import ValidationError
from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from eth2._utils.bitfield import get_empty_bitfield, has_voted
from eth2._utils.bls import bls
from eth2._utils.bls.backends.chia import ChiaBackend
from eth2._utils.bls.backends.milagro import MilagroBackend
from eth2.beacon.helpers import compute_domain
from eth2.beacon.signature_domain import SignatureDomain
from eth2.beacon.tools.builder.validator import aggregate_votes, verify_votes


@pytest.mark.slow
@settings(max_examples=1, deadline=None)
@given(random=st.randoms())
@pytest.mark.parametrize(("votes_count"), [(0), (9)])
def test_aggregate_votes(votes_count, random, privkeys, pubkeys):
    bit_count = 10
    pre_bitfield = get_empty_bitfield(bit_count)
    pre_sigs = ()
    domain = compute_domain(SignatureDomain.DOMAIN_ATTESTATION)

    random_votes = random.sample(range(bit_count), votes_count)
    message_hash = b"\x12" * 32

    # Get votes: (committee_index, sig, public_key)
    votes = [
        (
            committee_index,
            bls.sign(message_hash, privkeys[committee_index], domain),
            pubkeys[committee_index],
        )
        for committee_index in random_votes
    ]

    # Verify
    sigs, committee_indices = verify_votes(message_hash, votes, domain)

    # Aggregate the votes
    bitfield, sigs = aggregate_votes(
        bitfield=pre_bitfield,
        sigs=pre_sigs,
        voting_sigs=sigs,
        attesting_indices=committee_indices,
    )

    try:
        _, _, pubs = zip(*votes)
    except ValueError:
        pubs = ()

    voted_index = [
        committee_index
        for committee_index in random_votes
        if has_voted(bitfield, committee_index)
    ]
    assert len(voted_index) == len(votes)

    aggregated_pubs = bls.aggregate_pubkeys(pubs)

    if votes_count == 0 and bls.backend in (ChiaBackend, MilagroBackend):
        with pytest.raises(ValidationError):
            bls.validate(message_hash, aggregated_pubs, sigs, domain)
    else:
        bls.validate(message_hash, aggregated_pubs, sigs, domain)
