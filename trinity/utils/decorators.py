from typing import (
    Any,
)


class classproperty(property):
    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        return super().__get__(objtype)
