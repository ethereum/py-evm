from typing import (
    Tuple,
    Type,
    TypeVar,
)

from eth.rlp.blocks import (
    BaseBlock,
)
from eth.rlp.headers import (
    BlockHeader,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
    Endpoint,
)

from p2p.service import (
    BaseService,
)

from trinity.chains.base import (
    BaseAsyncChain,
)
from trinity.utils.async_errors import (
    await_and_wrap_errors,
)


class BaseChainResponse(BaseEvent):

    def __init__(self, error: Exception) -> None:
        self.error = error


class ImportBlockResponse(BaseChainResponse):

    def __init__(self,
                 response: Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]],
                 error: Exception=None) -> None:
        super().__init__(error)
        self.response = response


class ImportBlockRequest(BaseRequestResponseEvent[ImportBlockResponse]):

    def __init__(self, block: BaseBlock, perform_validation: bool = True) -> None:
        self.block = block
        self.perform_validation = True

    @staticmethod
    def expected_response_type() -> Type[ImportBlockResponse]:
        return ImportBlockResponse


class BlockImportHandler(BaseService):
    """
    The ``BlockImportHandler`` receives blocks through certain events on the eventbus and delegates
    them to a local ``Chain`` to import them. This handler is meant to run in a seperate process
    since block importing is a rather costly operation.
    """

    def __init__(self,
                 chain: BaseAsyncChain,
                 event_bus: Endpoint) -> None:
        super().__init__()
        self.chain = chain
        self.event_bus = event_bus

    async def _run(self) -> None:
        self.logger.info("Running BlockImporter")

        self.run_daemon_task(self.handle_import_block_requests())

    async def handle_import_block_requests(self) -> None:
        async for event in self.event_bus.stream(ImportBlockRequest):

            self.logger.debug("Importing block: %s", event.block)
            val, error = await await_and_wrap_errors(
                self.chain.coro_import_block(event.block, event.perform_validation)
            )

            self.event_bus.broadcast(
                event.expected_response_type()(val, error),
                event.broadcast_config()
            )


class EventBusBlockImporter:
    """
    The ``EventBusBlockImporter`` is a thin API on top of the ``EventBus`` that delegates blocks
    to an isolated process, dedicated entirely for block importing.
    """

    def __init__(self, event_bus: Endpoint) -> None:
        self.event_bus = event_bus

    async def coro_import_block(self,
                                block: BlockHeader,
                                perform_validation: bool=True,
                                ) -> Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]:

        event = ImportBlockRequest(block, perform_validation)
        # TODO: We need to teach Lahja to accept a BroadcastConfig for `request`
        # to make that more efficient. Without that, blocks are broadcasted across
        # all connected processes, even though *we know* that they are only meant
        # to be processed by one specific interested party.
        return self._pass_or_raise(await self.event_bus.request(event)).response

    TResponse = TypeVar("TResponse", bound=BaseChainResponse)

    def _pass_or_raise(self, response: TResponse) -> TResponse:
        if response.error is not None:
            raise response.error

        return response
