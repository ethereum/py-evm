from abc import ABC, abstractmethod
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterator,
    Tuple,
    Type,
    TYPE_CHECKING,
)

from eth_typing import BlockIdentifier

from eth.rlp.headers import BlockHeader
from p2p.peer import BasePeer

from trinity.protocol.common.exchanges import (
    BaseExchange,
)
from trinity.protocol.common.managers import (
    ExchangeManager,
)


class BaseExchangeHandler(ABC):
    @property
    @abstractmethod
    def _exchange_config(self) -> Dict[str, Type[BaseExchange[Any, Any, Any]]]:
        pass

    def __init__(self, peer: BasePeer) -> None:
        self._peer = peer

        for attr, exchange_cls in self._exchange_config.items():
            if hasattr(self, attr):
                raise AttributeError(
                    f"Unable to set manager on attribute `{attr}` which is already "
                    f"present on the class: {getattr(self, attr)}"
                )
            manager: ExchangeManager[Any, Any, Any]
            manager = ExchangeManager(self._peer, exchange_cls.response_cmd_type, peer.cancel_token)
            exchange = exchange_cls(manager)
            setattr(self, attr, exchange)

    def __iter__(self) -> Iterator[BaseExchange[Any, Any, Any]]:
        for key in self._exchange_config.keys():
            yield getattr(self, key)

    def get_stats(self) -> Dict[str, str]:
        return {
            exchange.response_cmd_type.__name__: exchange.tracker.get_stats()
            for exchange
            in self
        }


if TYPE_CHECKING:
    from mypy_extensions import DefaultArg
    BlockHeadersCallable = Callable[
        [
            BaseExchangeHandler,
            BlockIdentifier,
            int,
            DefaultArg(int, 'skip'),
            DefaultArg(int, 'reverse')
        ],
        Awaitable[Tuple[BlockHeader, ...]]
    ]


# This class is only needed to please mypy for type checking
class BaseChainExchangeHandler(BaseExchangeHandler):
    get_block_headers: 'BlockHeadersCallable'
