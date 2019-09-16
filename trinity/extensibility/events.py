from dataclasses import (
    dataclass,
)
from typing import (
    Type,
    TYPE_CHECKING,
)

from lahja import (
    BaseEvent,
)


if TYPE_CHECKING:
    from trinity.extensibility import (  # noqa: F401
        BaseComponent,
    )


@dataclass
class ComponentStartedEvent(BaseEvent):
    """
    Broadcasted when a component was started
    """

    component_type: Type['BaseComponent']
