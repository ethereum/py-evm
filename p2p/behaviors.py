from abc import abstractmethod
import logging
from typing import (
    AsyncIterator,
    Callable,
    Tuple,
    Type,
)

from async_generator import asynccontextmanager

from async_exit_stack import AsyncExitStack

from p2p.abc import (
    BehaviorAPI,
    CommandAPI,
    CommandHandlerFn,
    ConnectionAPI,
)
from p2p.typing import Payload


class CommandHandler(BehaviorAPI):
    """
    Base class to reduce boilerplate for Behaviors that want to register a
    handler against a single command.
    """
    cmd_type: Type[CommandAPI]
    logger = logging.getLogger('p2p.behaviors.CommandHandler')

    def applies_to(self, connection: ConnectionAPI) -> bool:
        return any(
            protocol.supports_command(self.cmd_type)
            for protocol
            in connection.get_multiplexer().get_protocols()
        )

    def on_apply(self, connection: ConnectionAPI) -> None:
        """
        Hook for subclasses to perform some action once the behavior has been
        applied to the connection.
        """
        pass

    @asynccontextmanager
    async def apply(self, connection: ConnectionAPI) -> AsyncIterator[None]:
        if self.cmd_type is None:
            raise TypeError(f"No cmd_type specified for {self}")

        with connection.add_command_handler(self.cmd_type, self.handle):
            self.on_apply(connection)
            yield

    @abstractmethod
    async def handle(self, connection: ConnectionAPI, msg: Payload) -> None:
        ...


def command_handler(command_type: Type[CommandAPI],
                    *,
                    name: str = None) -> Callable[[CommandHandlerFn], Type[CommandHandler]]:
    """
    Decorator that can be used to construct a CommandHandler from a simple
    function.

    .. code-block:: python

        @command_handler(Ping)
        def handle_ping(connection, msg):
            connection.get_base_protocol().send_pong()
    """
    if name is None:
        name = f'handle_{command_type.__name__}'

    def decorator(fn: CommandHandlerFn) -> Type[CommandHandler]:
        return type(
            name,
            (CommandHandler,),
            {
                'cmd_type': command_type,
                'handle': staticmethod(fn),
            },
        )
    return decorator


class ConnectionBehavior(BehaviorAPI):
    """
    Base class to simply give access to the `ConnectionAPI`.  It is up to
    subclasses to implement `applies_to`.  This is primarily for implementing
    APIs for interacting with the connection object.

    .. code-block:: python

        class Disconnect(ConnectionBehavior):
            def applies_to(self, connection):
                return True

            def __call__(self, reason: DisconnectReason):
                self._connection.get_base_protocol().send_disconnect(reason)
    """
    @asynccontextmanager
    async def apply(self, connection: ConnectionAPI) -> AsyncIterator[None]:
        if hasattr(self, '_connection'):
            raise Exception("Reentrance!")
        self._connection = connection
        yield


class Application(BehaviorAPI):
    """
    Wrapper arround a collection of behaviors.  Primarily used to aggregate
    multiple smaller units of functionality.

    When applied an `Application` registers itself with the `ConnectionAPI`
    under the defined `name`.
    """
    name: str

    @abstractmethod
    def get_behaviors(self) -> Tuple[BehaviorAPI, ...]:
        ...

    def on_apply(self, connection: ConnectionAPI) -> None:
        """
        Hook for subclasses to perform some action once the behavior has been
        applied to the connection.
        """
        pass

    def applies_to(self, connection: ConnectionAPI) -> bool:
        return any(
            behavior.applies_to(connection)
            for behavior
            in self.get_behaviors()
        )

    @asynccontextmanager
    async def apply(self, connection: ConnectionAPI) -> AsyncIterator[None]:
        if hasattr(self, '_connection') is True:
            raise Exception("Reentrance!")

        self._connection = connection

        async with AsyncExitStack() as stack:
            for behavior in self.get_behaviors():
                if behavior.applies_to(connection):
                    await stack.enter_async_context(behavior.apply(connection))

            with connection.add_api(self.name, self):
                self.on_apply(connection)
                yield
