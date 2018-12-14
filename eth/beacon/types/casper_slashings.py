import rlp
from .slashable_vote_data import SlashableVoteData


class CasperSlashing(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # First batch of votes
        ('slashable_vote_data_1', SlashableVoteData),
        # Second batch of votes
        ('slashable_vote_data_2', SlashableVoteData),
    ]

    def __init__(self,
                 slashable_vote_data_1: SlashableVoteData,
                 slashable_vote_data_2: SlashableVoteData)-> None:
        super().__init__(
            slashable_vote_data_1,
            slashable_vote_data_2,
        )
