from typing import (
    Union,
)

from eth_typing import (
    BlockNumber,
)
from eth_utils import (
    is_integer,
)

from eth.rlp.headers import (
    BlockHeader,
)

from trinity.chains.base import AsyncChainAPI


async def get_header(chain: AsyncChainAPI, at_block: Union[str, int]) -> BlockHeader:
    if at_block == 'pending':
        raise NotImplementedError("RPC interface does not support the 'pending' block at this time")
    elif at_block == 'latest':
        at_header = chain.get_canonical_head()
    elif at_block == 'earliest':
        # TODO find if genesis block can be non-zero. Why does 'earliest' option even exist?
        block = await chain.coro_get_canonical_block_by_number(BlockNumber(0))
        at_header = block.header
    # mypy doesn't have user defined type guards yet
    # https://github.com/python/mypy/issues/5206
    elif is_integer(at_block) and at_block >= 0:  # type: ignore
        block = await chain.coro_get_canonical_block_by_number(BlockNumber(int(at_block)))
        at_header = block.header
    else:
        raise TypeError("Unrecognized block reference: %r" % at_block)

    return at_header
