from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterator,
    Tuple,
    TYPE_CHECKING,
)

from eth_typing import BlockIdentifier

from eth.rlp.headers import BlockHeader


from eth_utils import ValidationError

from p2p.abc import ConnectionAPI
from p2p.exceptions import UnknownProtocol

from .abc import ExchangeAPI, HandlerAPI
from .managers import ExchangeManager


class BaseExchangeHandler(HandlerAPI):
    def __init__(self, connection: ConnectionAPI) -> None:
        self._connection = connection

        available_protocols = self._connection.get_multiplexer().get_protocols()
        for attr, exchange_cls in self._exchange_config.items():
            if hasattr(self, attr):
                raise AttributeError(
                    f"Unable to set manager on attribute `{attr}` which is already "
                    f"present on the class: {getattr(self, attr)}"
                )

            # determine which protocol should be used to issue requests
            supported_protocols = tuple(
                protocol
                for protocol in available_protocols
                if protocol.supports_command(exchange_cls.get_request_cmd_type())
            )
            if len(supported_protocols) == 1:
                protocol_type = type(supported_protocols[0])
            elif not supported_protocols:
                raise UnknownProtocol(
                    f"Connection does not have any protocols that support the "
                    f"request command: {exchange_cls.get_request_cmd_type()}"
                )
            elif len(supported_protocols) > 1:
                raise ValidationError(
                    f"Could not determine appropriate protocol for command: "
                    f"{exchange_cls.get_request_cmd_type()}.  Command was found in the "
                    f"protocols {supported_protocols}"
                )
            else:
                raise Exception("This code path should be unreachable")

            if not protocol_type.supports_command(exchange_cls.get_response_cmd_type()):
                raise ValidationError(
                    f"Could not determine appropriate protocol: "
                    f"The response command type "
                    f"{exchange_cls.get_response_cmd_type()} is not supported by the "
                    f"protocol that matched the request command type: "
                    f"{protocol_type}"
                )

            manager: ExchangeManager[Any, Any, Any]
            manager = ExchangeManager(
                connection=self._connection,
                requesting_on=protocol_type,
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
