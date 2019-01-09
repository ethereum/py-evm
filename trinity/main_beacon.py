from argparse import Namespace
import asyncio
import logging
import signal
from typing import (
    Any,
    Dict,
)

from lahja import (
    EventBus,
    Endpoint,
)

from trinity.bootstrap import (
    kill_trinity_gracefully,
    main_entry,
)
from trinity.config import (
    TrinityConfig,
    BeaconAppConfig
)
from trinity.constants import (
    APP_IDENTIFIER_BEACON,
)
from trinity.events import (
    ShutdownRequest
)
from trinity.extensibility import (
    PluginManager,
)
from trinity.plugins.registry import (
    BASE_PLUGINS,
)


def main_beacon() -> None:
    main_entry(trinity_boot, APP_IDENTIFIER_BEACON, BASE_PLUGINS, (BeaconAppConfig,))


def trinity_boot(args: Namespace,
                 trinity_config: TrinityConfig,
                 extra_kwargs: Dict[str, Any],
                 plugin_manager: PluginManager,
                 listener: logging.handlers.QueueListener,
                 event_bus: EventBus,
                 main_endpoint: Endpoint,
                 logger: logging.Logger) -> None:
    # start the listener thread to handle logs produced by other processes in
    # the local logger.
    listener.start()

    event_bus.start()

    def kill_trinity_with_reason(reason: str) -> None:
        kill_trinity_gracefully(
            logger,
            (),
            plugin_manager,
            main_endpoint,
            event_bus,
            reason=reason
        )

    main_endpoint.subscribe(
        ShutdownRequest,
        lambda ev: kill_trinity_with_reason(ev.reason)
    )

    plugin_manager.prepare(args, trinity_config, extra_kwargs)

    try:
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: kill_trinity_with_reason("SIGTERM"))
        loop.run_forever()
        loop.close()
    except KeyboardInterrupt:
        kill_trinity_with_reason("CTRL+C / Keyboard Interrupt")
