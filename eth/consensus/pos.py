from typing import (
    Iterable,
)

from eth.abc import (
    AtomicDatabaseAPI,
    BlockHeaderAPI,
    ConsensusAPI,
)
from eth.typing import (
    Address,
)


class PosConsensus(ConsensusAPI):
    """
    Proof of Stake (PoS) consensus is not achieved in the execution layer (EL).
    This consensus class basically implements the same rules as ``NoProofConsensus``
    but with a more proper distinction.
    """

    def __init__(self, base_db: AtomicDatabaseAPI) -> None:
        pass

    def validate_seal(self, header: BlockHeaderAPI) -> None:
        pass

    def validate_seal_extension(
        self, header: BlockHeaderAPI, parents: Iterable[BlockHeaderAPI]
    ) -> None:
        pass

    @classmethod
    def get_fee_recipient(cls, header: BlockHeaderAPI) -> Address:
        return header.coinbase
