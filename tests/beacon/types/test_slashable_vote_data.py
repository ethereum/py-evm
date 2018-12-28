from eth.beacon.types.slashable_vote_data import (
    SlashableVoteData,
)


def test_defaults(sample_slashable_vote_data_params):
    votes = SlashableVoteData(**sample_slashable_vote_data_params)

    assert (votes.aggregate_signature_poc_0_indices ==
            sample_slashable_vote_data_params['aggregate_signature_poc_0_indices'])
    assert (votes.aggregate_signature_poc_1_indices ==
            sample_slashable_vote_data_params['aggregate_signature_poc_1_indices'])
    assert votes.data == sample_slashable_vote_data_params['data']
    assert votes.aggregate_signature == sample_slashable_vote_data_params['aggregate_signature']


def test_hash(sample_slashable_vote_data_params):
    votes = SlashableVoteData(**sample_slashable_vote_data_params)

    # NOTE: this hash was simply copied from the existing implementation
    # which should be the keccak-256 of the rlp serialization of `votes`.
    # Given that this value will change soon (cf. ssz tree hash), we just
    # do this to get the test passing for now and will need to update later
    # if we expect the hash computation is not working correctly
    hash_hex = "7e4b4cf3ac47988865d693a29b6aa5a825f27e065cf21a80af5e077ea102e297"

    assert votes.hash == bytes.fromhex(hash_hex)


def test_root(sample_slashable_vote_data_params):
    votes = SlashableVoteData(**sample_slashable_vote_data_params)

    # NOTE: see note in `test_hash`, this test will need to be updated
    # once ssz tree hash lands...

    assert votes.root == votes.hash


def test_vote_count(sample_slashable_vote_data_params):
    votes = SlashableVoteData(**sample_slashable_vote_data_params)

    key = "aggregate_signature_poc_0_indices"
    proof_of_custody_0_indices = sample_slashable_vote_data_params[key]
    key = "aggregate_signature_poc_1_indices"
    proof_of_custody_1_indices = sample_slashable_vote_data_params[key]

    assert votes.vote_count == len(proof_of_custody_0_indices) + len(proof_of_custody_1_indices)


def test_messages(sample_slashable_vote_data_params):
    votes = SlashableVoteData(**sample_slashable_vote_data_params)

    zero_discriminator = (0).to_bytes(1, 'big')
    one_discriminator = (1).to_bytes(1, 'big')

    assert votes.messages == (
        votes.root + zero_discriminator,
        votes.root + one_discriminator,
    )
