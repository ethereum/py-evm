from typing import Any, Callable, Coroutine, TypeVar
import types

TReturn = TypeVar("TReturn")


def async_passthrough(method: Callable[..., TReturn],
                      ) -> Callable[..., Coroutine[Any, Any, TReturn]]:
    coro_name = 'coro_{0}'.format(method.__name__)

    async def passthrough_method(self: Any, *args: Any, **kwargs: Any) -> TReturn:
        cls_method = getattr(self, method.__name__)

        if isinstance(cls_method, types.MethodType):
            # we need to call the classmethods from the actual cls
            return cls_method(*args, **kwargs)
        elif isinstance(cls_method, types.FunctionType):
            return cls_method(self, *args, **kwargs)
        else:
            raise Exception("Invariant")

    passthrough_method.__name__ = coro_name
    return passthrough_method
