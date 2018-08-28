from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Iterable,
    Type,
)

from eth_utils import to_tuple

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

    # https://github.com/python/mypy/issues/1362
    @property  # type: ignore
    @to_tuple
    def exchanges(self) -> Iterable[Type[BaseExchange[Any, Any, Any]]]:
        for key in self._exchange_config:
            yield getattr(self, key)

    def __init__(self, peer: BasePeer) -> None:
        self._peer = peer

        for attr, exchange_cls in self._exchange_config.items():
            if hasattr(self, attr):
                raise AttributeError(
                    "Unable to set manager on attribute `{0}` which is already "
                    "present on the class: {1}".format(attr, getattr(self, attr))
                )
            manager: ExchangeManager[Any, Any, Any]
            manager = ExchangeManager(self._peer, exchange_cls.response_cmd_type, peer.cancel_token)
            exchange = exchange_cls(manager)
            setattr(self, attr, exchange)

    def get_stats(self) -> Dict[str, str]:
        return {
            exchange.response_cmd_type.__name__: exchange.tracker.get_stats()
            for exchange
            in self.exchanges
        }
