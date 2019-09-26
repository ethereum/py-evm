from typing import NamedTuple, Union

from eth_typing import BlockNumber, Hash32


class BlockHeadersQuery(NamedTuple):
    block_number_or_hash: Union[BlockNumber, Hash32]
    max_headers: int
    skip: int
    reverse: bool
