from trinity.exceptions import (
    BaseTrinityError,
)


class UnsuitableShutdownError(BaseTrinityError):
    """
    Raised when `shutdown` was called on a ``PluginManager`` instance that operates
    in the ``MainAndIsolatedProcessScope`` or when ``shutdown_blocking`` was called on a
    ``PluginManager`` instance that operates in the ``SharedProcessScope``.
    """
    pass
