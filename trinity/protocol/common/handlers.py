from abc import abstractmethod
from typing import (
    Any,
    Dict,
    Type,
)

from cancel_token import CancelToken

from p2p.peer import BasePeer
from p2p.service import (
    BaseService,
    ServiceContext,
)

from .managers import BaseRequestManager


class BaseRequestResponseHandler(BaseService):
    @property
    @abstractmethod
    def _managers(self) -> Dict[str, Type[BaseRequestManager[Any, Any, Any, Any]]]:
        pass

    def __init__(self, peer: BasePeer, context: ServiceContext, token: CancelToken) -> None:
        super().__init__(context, token)

        self._peer = peer

        for attr, request_manager_cls in self._managers.items():
            if hasattr(self, attr):
                raise AttributeError(
                    "Unable to set manager on attribute `{0}` which is already "
                    "present on the class: {1}".format(attr, getattr(self, attr))
                )
            manager = request_manager_cls(self._peer, self.context, self.cancel_token)
            setattr(self, attr, manager)

    async def _run(self) -> None:
        for attr in self._managers.keys():
            manager = getattr(self, attr)
            self.run_child_service(manager)

        await self.cancel_token.wait()

    async def _cleanup(self) -> None:
        pass
