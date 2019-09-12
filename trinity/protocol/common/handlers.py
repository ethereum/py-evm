from typing import (
    Awaitable,
    Callable,
    Tuple,
    TYPE_CHECKING,
)

from eth_typing import BlockIdentifier

from eth.rlp.headers import BlockHeader

from p2p.exchange import BaseExchangeHandler


if TYPE_CHECKING:
    from mypy_extensions import DefaultArg
    BlockHeadersCallable = Callable[
        [
            BaseExchangeHandler,
            BlockIdentifier,
            DefaultArg(int, 'max_headers'),
            DefaultArg(int, 'skip'),
            DefaultArg(int, 'reverse'),
            DefaultArg(float, 'timeout')
        ],
        Awaitable[Tuple[BlockHeader, ...]]
    ]


# This class is only needed to please mypy for type checking
class BaseChainExchangeHandler(BaseExchangeHandler):
    get_block_headers: 'BlockHeadersCallable'
