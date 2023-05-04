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


class NoProofConsensus(ConsensusAPI):
    """
    Modify a set of VMs to accept blocks without any validation.
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
