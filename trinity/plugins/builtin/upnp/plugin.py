from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio


from p2p.nat import (
    UPnPService,
)

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility import (
    BaseIsolatedPlugin,
)
from trinity._utils.shutdown import (
    exit_with_endpoint_and_services,
)


class UpnpPlugin(BaseIsolatedPlugin):
    """
    Continously try to map external to internal ip address/port using the
    Universal Plug 'n' Play (upnp) standard.
    """

    @property
    def name(self) -> str:
        return "Upnp"

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
        self.start()

    @classmethod
    def configure_parser(cls,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--disable-upnp",
            action="store_true",
            help="Disable upnp mapping",
        )

    def do_start(self) -> None:
        port = self.boot_info.trinity_config.port
        self.upnp_service = UPnPService(port)
        asyncio.ensure_future(exit_with_endpoint_and_services(self.event_bus, self.upnp_service))
        asyncio.ensure_future(self.upnp_service.run())
