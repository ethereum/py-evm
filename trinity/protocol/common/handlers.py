from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Iterator,
    Type,
)

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
                    "Unable to set manager on attribute `{0}` which is already "
                    "present on the class: {1}".format(attr, getattr(self, attr))
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
