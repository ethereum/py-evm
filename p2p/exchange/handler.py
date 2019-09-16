from typing import (
    Any,
    Dict,
    Iterator,
)

from eth_utils import ValidationError

from p2p.abc import ConnectionAPI

from .abc import ExchangeAPI, HandlerAPI
from .manager import ExchangeManager


class BaseExchangeHandler(HandlerAPI):
    def __init__(self, connection: ConnectionAPI) -> None:
        self._connection = connection

        for attr, exchange_cls in self._exchange_config.items():
            if hasattr(self, attr):
                raise AttributeError(
                    f"Unable to set manager on attribute `{attr}` which is already "
                    f"present on the class: {getattr(self, attr)}"
                )

            protocol = connection.get_protocol_for_command_type(
                exchange_cls.get_request_cmd_type()
            )

            if not protocol.supports_command(exchange_cls.get_response_cmd_type()):
                raise ValidationError(
                    f"Could not determine appropriate protocol: "
                    f"The response command type "
                    f"{exchange_cls.get_response_cmd_type()} is not supported by the "
                    f"protocol that matched the request command type: "
                    f"{protocol}"
                )

            manager: ExchangeManager[Any, Any, Any]
            manager = ExchangeManager(
                connection=self._connection,
                requesting_on=protocol,
                listening_for=exchange_cls.get_response_cmd_type(),
            )
            exchange = exchange_cls(manager)
            setattr(self, attr, exchange)

    def __iter__(self) -> Iterator[ExchangeAPI[Any, Any, Any]]:
        for key in self._exchange_config.keys():
            yield getattr(self, key)

    def get_stats(self) -> Dict[str, str]:
        return {
            exchange.get_response_cmd_type().__name__: exchange.tracker.get_stats()
            for exchange
            in self
        }
