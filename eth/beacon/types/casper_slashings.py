import rlp
from .slashable_vote_data import SlashableVoteData


class CasperSlashing(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # First batch of votes
        ('votes_1', SlashableVoteData),
        # Second batch of votes
        ('votes_2', SlashableVoteData),
    ]

    def __init__(self,
                 votes_1: SlashableVoteData,
                 votes_2: SlashableVoteData)-> None:
        super().__init__(
            votes_1,
            votes_2,
        )
