import abc
from typing import Generic, Sized, TypeVar

HandlerType = TypeVar("HandlerType", bound=Sized)


class TestType(abc.ABC, Generic[HandlerType]):
    name: str
    handlers: HandlerType
