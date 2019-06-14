from dataclasses import (
    dataclass,
)
from typing import (
    Any,
    Type,
    TYPE_CHECKING,
)

from lahja import (
    BaseEvent,
)


if TYPE_CHECKING:
    from trinity.extensibility import (  # noqa: F401
        BasePlugin,
    )


@dataclass
class PluginStartedEvent(BaseEvent):
    """
    Broadcasted when a plugin was started
    """

    plugin_type: Type['BasePlugin']


@dataclass
class ResourceAvailableEvent(BaseEvent):
    """
    Broadcasted when a resource becomes available
    """

    resource: Any
    resource_type: Type[Any]
