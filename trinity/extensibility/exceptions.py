from trinity.exceptions import (
    BaseTrinityError,
)


class InvalidPluginStatus(BaseTrinityError):
    """
    Raised when it was attempted to perform an action while the current
    :class:`~trinity.extensibility.plugin.PluginStatus` does not allow to perform such action.
    """
    pass


class UnsuitableShutdownError(BaseTrinityError):
    """
    Raised when :meth:`~trinity.extensibility.plugin_manager.PluginManager.shutdown` was called on
    a :class:`~trinity.extensibility.plugin_manager.PluginManager` instance that operates in the
    :class:`~trinity.extensibility.plugin_manager.MainAndIsolatedProcessScope` or when
    :meth:`~trinity.extensibility.plugin.PluginManager.shutdown_blocking` was called on a
    :class:`~trinity.extensibility.plugin_manager.PluginManager` instance that operates in the
    :class:`~trinity.extensibility.plugin_manager.SharedProcessScope`.
    """
    pass
