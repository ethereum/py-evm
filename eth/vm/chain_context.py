from typing import (
    Optional,
)

from eth.abc import (
    ChainContextAPI,
)
from eth.validation import (
    validate_uint256,
)


class ChainContext(ChainContextAPI):
    __slots__ = ["_chain_id"]

    def __init__(self, chain_id: Optional[int]) -> None:
        if chain_id is None:
            chain_id = 0  # Default value (invalid for public networks)
        # Due to EIP-155's definition of Chain ID,
        # the number that needs to be RLP encoded is `CHAINID * 2 + 36`
        validate_uint256(chain_id)
        self._chain_id = chain_id

    @property
    def chain_id(self) -> int:
        return self._chain_id
