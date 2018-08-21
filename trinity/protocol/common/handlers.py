from abc import abstractmethod
from typing import (
    Any,
    Dict,
    List,
    Set,
    Type,
)

from p2p.peer import BasePeer

from trinity.protocol.common.exchanges import (
    BaseExchange,
)
from trinity.protocol.common.managers import (
    ExchangeManager,
)


class BaseExchangeHandler:
    _exchange_managers: Set[ExchangeManager[Any, Any, Any]]

    @property
    @abstractmethod
    def _exchanges(self) -> Dict[str, Type[BaseExchange[Any, Any, Any]]]:
        pass

    def __init__(self, peer: BasePeer) -> None:
        self._peer = peer
        self._exchange_managers = set()

        for attr, exchange_cls in self._exchanges.items():
            if hasattr(self, attr):
                raise AttributeError(
                    "Unable to set manager on attribute `{0}` which is already "
                    "present on the class: {1}".format(attr, getattr(self, attr))
                )
            manager: ExchangeManager[Any, Any, Any] = ExchangeManager(self._peer, peer.cancel_token)
            self._exchange_managers.add(manager)
            exchange = exchange_cls(manager)
            setattr(self, attr, exchange)

    def get_stats(self) -> List[str]:
        return [exchange_manager.get_stats() for exchange_manager in self._exchange_managers]
