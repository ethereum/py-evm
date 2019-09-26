from abc import ABC, abstractmethod
from typing import (
    Any,
    Type,
    TypeVar,
)

from p2p.abc import (
    CommandAPI,
    ConnectionAPI,
    LogicAPI,
    ProtocolAPI,
    QualifierFn,
)

TQualifierFn = TypeVar("TQualifierFn", bound=QualifierFn)


class BaseQualifier(ABC):
    def __and__(self, other: QualifierFn) -> 'BaseQualifier':
        return AndQualifier(self, other)

    def __or__(self, other: QualifierFn) -> 'BaseQualifier':
        return OrQualifier(self, other)

    @abstractmethod
    def __call__(self, connection: ConnectionAPI, logic: LogicAPI) -> bool:
        ...


def qualifier(fn: QualifierFn) -> QualifierFn:
    return type(
        f'Qualifier[{fn.__name__}]',
        (BaseQualifier,),
        {'__call__': staticmethod(fn)},
    )()


class AndQualifier(BaseQualifier):
    def __init__(self, *qualifiers: QualifierFn) -> None:
        if not qualifiers:
            raise TypeError("Non-empty qualifiers required")
        self._qualifiers = qualifiers

    def __call__(self, connection: ConnectionAPI, logic: LogicAPI) -> bool:
        return all(qualifier(connection, logic) for qualifier in self._qualifiers)


class OrQualifier(BaseQualifier):
    def __init__(self, *qualifiers: QualifierFn) -> None:
        if not qualifiers:
            raise TypeError("Non-empty qualifiers required")
        self._qualifiers = qualifiers

    def __call__(self, connection: ConnectionAPI, logic: LogicAPI) -> bool:
        return any(qualifier(connection, logic) for qualifier in self._qualifiers)


class HasProtocol(BaseQualifier):
    def __init__(self, protocol_type: Type[ProtocolAPI]) -> None:
        self._protocol_type = protocol_type

    def __call__(self, connection: ConnectionAPI, logic: LogicAPI) -> bool:
        return connection.has_protocol(self._protocol_type)

    def __str__(self) -> str:
        return f"<HasProtocol[{self._protocol_type.name}/{self._protocol_type.version}]>"

    def __repr__(self) -> str:
        return f"HasProtocol(self._protocol_type.__name__)"


class HasCommand(BaseQualifier):
    def __init__(self, command_type: Type[CommandAPI[Any]]) -> None:
        self._command_type = command_type

    def __call__(self, connection: ConnectionAPI, logic: LogicAPI) -> bool:
        return any(
            protocol.supports_command(self._command_type)
            for protocol
            in connection.get_protocols()
        )

    def __str__(self) -> str:
        return f"<HasCommand[{self._command_type.__name__}]>"

    def __repr__(self) -> str:
        return f"HasCommand(self._command_type.__name__)"


@qualifier
def always(connection: ConnectionAPI, logic: LogicAPI) -> bool:
    """
    A `QualifierFn` that always returns `True`
    """
    return True
