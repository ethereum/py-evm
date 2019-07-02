from trinity.exceptions import (
    BaseTrinityError,
)


class InvalidPluginStatus(BaseTrinityError):
    """
    Raised when it was attempted to perform an action while the current
    :class:`~trinity.extensibility.plugin.PluginStatus` does not allow to perform such action.
    """
    pass
