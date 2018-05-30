# Tell mypy to ignore this import as a workaround for https://github.com/python/mypy/issues/4049
from trinity.rpc.modules import (  # type: ignore
    RPCModule,
)


class Net(RPCModule):
    def version(self):
        """
        Returns the current network ID.
        """
        return str(self._chain.network_id)
