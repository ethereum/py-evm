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

    def validate_seal(self,
                      header: BlockHeaderAPI,
                      cached_parents: Iterable[BlockHeaderAPI] = ()) -> None:
        """
        Validate the seal on the given header.
        """
        return

    @classmethod
    def get_fee_recipient(cls, header: BlockHeaderAPI) -> Address:
        return header.coinbase
