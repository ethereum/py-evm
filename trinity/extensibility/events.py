from typing import (
    Any,
    Type,
    TYPE_CHECKING,
)
from argparse import (
    Namespace,
)

from trinity.config import (
    ChainConfig,
)


if TYPE_CHECKING:
    from trinity.extensibility import (  # noqa: F401
        BasePlugin,
    )


class BaseEvent:
    """
    The base class for all plugin events. Plugin events can be broadcasted for all different
    kind of reasons. Plugins can act based on these events and consume the events even before
    the plugin is started, giving plugins the chance to start based on an event or a series of
    events. The startup of Trinity itself can be an event as well as the start of a plugin itself
    which, for instance, gives other plugins the chance to start based on these previous events.
    """
    pass


class TrinityStartupEvent(BaseEvent):
    """
    Broadcasted when Trinity is starting.
    """
    def __init__(self, args: Namespace, chain_config: ChainConfig) -> None:
        self.args = args
        self.chain_config = chain_config


class PluginStartedEvent(BaseEvent):
    """
    Broadcasted when a plugin was started
    """
    def __init__(self, plugin: 'BasePlugin') -> None:
        self.plugin = plugin


class ResourceAvailableEvent(BaseEvent):
    """
    Broadcasted when a resource becomes available
    """
    def __init__(self, resource: Any, resource_type: Type[Any]) -> None:
        self.resource = resource
        self.resource_type = resource_type
