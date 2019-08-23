from typing import Optional

from eth.abc import ChainContextAPI
from eth.validation import (
    validate_uint64,
)


class ChainContext(ChainContextAPI):
    """
    This immutable object houses chain information that remains constant for the entire context of
    the VM execution.
    """
    __slots__ = ['_chain_id']

    def __init__(self, chain_id: Optional[int]) -> None:

        if chain_id is None:
            chain_id = 0  # Default value (invalid for public networks)
        # Due to EIP-155's definition of chain IDs, the max number is UINT256_MAX/2 - 36,
        #   so the recommended space for chain ID is uint64.
        validate_uint64(chain_id)
        self._chain_id = chain_id

    @property
    def chain_id(self) -> int:
        return self._chain_id
