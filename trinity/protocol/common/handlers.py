from abc import abstractmethod
from typing import (
    Any,
    Dict,
    List,
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
    @property
    @abstractmethod
    def _exchanges(self) -> Dict[str, Type[BaseExchange[Any, Any, Any]]]:
        pass

    def __init__(self, peer: BasePeer) -> None:
        self._peer = peer

        for attr, exchange_cls in self._exchanges.items():
            if hasattr(self, attr):
                raise AttributeError(
                    "Unable to set manager on attribute `{0}` which is already "
                    "present on the class: {1}".format(attr, getattr(self, attr))
                )
            manager: ExchangeManager[Any, Any, Any] = ExchangeManager(self._peer, peer.cancel_token)
            exchange = exchange_cls(manager)
            setattr(self, attr, exchange)

    def get_stats(self) -> List[str]:
        manager_attrs = self._exchanges.keys()
        return [getattr(self, attr).get_stats() for attr in manager_attrs]
