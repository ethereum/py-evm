from typing import (
    AsyncIterator,
)

from async_generator import asynccontextmanager

from eth_utils import ValidationError

from p2p.abc import (
    LogicAPI,
    QualifierFn,
    BehaviorAPI,
    ConnectionAPI,
)


class Behavior(BehaviorAPI):
    """
    This class is primarily an internal API.  Users should rarely need to
    instantiate this class or modify its behavior.

    This class is responsible for:

    * combining the business logic from `LogicAPI` and a `QualifierFn` which
      decides whether the logic should be applied.
    * managing the lifecycle of the `LogicAPI`
    """
    _applied_to: ConnectionAPI = None

    def __init__(self, qualifier: QualifierFn, logic: LogicAPI) -> None:
        # mypy bug: https://github.com/python/mypy/issues/708
        self.qualifier = qualifier  # type: ignore
        self.logic = logic

    def should_apply_to(self, connection: 'ConnectionAPI') -> bool:
        # mypy bug: https://github.com/python/mypy/issues/708
        return self.qualifier(connection, self.logic)  # type: ignore

    @asynccontextmanager
    async def apply(self, connection: ConnectionAPI) -> AsyncIterator[None]:
        if self._applied_to is not None:
            raise ValidationError(
                f"Reentrance: Behavior has already been applied to a "
                f"connection: {self._applied_to}"
            )
        else:
            # this acts as re-entrance protection for for the `Behavior` instance.
            self._applied_to = connection

        if hasattr(self.logic, '_behavior'):
            raise ValidationError(
                f"Reentrance: Logic already bound to a behavior: "
                f"{self.logic._behavior}"
            )
        else:
            # this acts as re-entrance protection on the actual `LogicAPI` instance
            self.logic._behavior = self

        # once the logic is bound to the connection we enter it's context.
        async with self.logic.apply(connection):
            yield
