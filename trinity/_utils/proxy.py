from typing import (
    Any,
)
from multiprocessing.managers import (
    BaseManager,
)
import signal


def serve_until_sigint(manager: BaseManager) -> None:
    server = manager.get_server()  # type: ignore

    def _sigint_handler(*args: Any) -> None:
        server.stop_event.set()

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        server.serve_forever()
    except SystemExit:
        server.stop_event.set()
        raise
