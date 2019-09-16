from trinity.exceptions import (
    BaseTrinityError,
)


class InvalidComponentStatus(BaseTrinityError):
    """
    Raised when it was attempted to perform an action while the current
    :class:`~trinity.extensibility.component.ComponentStatus` does not allow to perform such action.
    """
    pass
