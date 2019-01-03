from eth.beacon.types.attestation_data_and_custody_bits import (
    AttestationDataAndCustodyBit,
)
from eth.beacon.types.slashable_vote_data import (
    SlashableVoteData,
)


def test_defaults(sample_slashable_vote_data_params):
    vote_data = SlashableVoteData(**sample_slashable_vote_data_params)

    assert (vote_data.custody_bit_0_indices ==
            sample_slashable_vote_data_params['custody_bit_0_indices'])
    assert (vote_data.custody_bit_1_indices ==
            sample_slashable_vote_data_params['custody_bit_1_indices'])
    assert vote_data.data == sample_slashable_vote_data_params['data']
    assert vote_data.aggregate_signature == sample_slashable_vote_data_params['aggregate_signature']


def test_hash(sample_slashable_vote_data_params):
    vote_data = SlashableVoteData(**sample_slashable_vote_data_params)

    # NOTE: this hash was simply copied from the existing implementation
    # which should be the keccak-256 of the rlp serialization of `votes`.
    # Given that this value will change soon (cf. ssz tree hash), we just
    # do this to get the test passing for now and will need to update later
    # if we expect the hash computation is not working correctly
    hash_hex = "7e4b4cf3ac47988865d693a29b6aa5a825f27e065cf21a80af5e077ea102e297"

    assert vote_data.hash == bytes.fromhex(hash_hex)


def test_root(sample_slashable_vote_data_params):
    vote_data = SlashableVoteData(**sample_slashable_vote_data_params)

    # NOTE: see note in `test_hash`, this test will need to be updated
    # once ssz tree hash lands...

    assert vote_data.root == vote_data.hash


def test_vote_count(sample_slashable_vote_data_params):
    vote_data = SlashableVoteData(**sample_slashable_vote_data_params)

    key = "custody_bit_0_indices"
    custody_bit_0_indices = sample_slashable_vote_data_params[key]
    key = "custody_bit_1_indices"
    custody_bit_1_indices = sample_slashable_vote_data_params[key]

    assert vote_data.vote_count == len(custody_bit_0_indices) + len(custody_bit_1_indices)


def test_messages(sample_slashable_vote_data_params):
    vote_data = SlashableVoteData(**sample_slashable_vote_data_params)

    assert vote_data.messages == (
        AttestationDataAndCustodyBit(vote_data.data, False).root,
        AttestationDataAndCustodyBit(vote_data.data, True).root,
    )
