import asyncio
from functools import partial
from typing import (
    Any,
    Callable,
    Optional,
    Tuple,
    Type,
    TypeVar,
)

from cancel_token import CancelToken
from eth.db.backends.base import BaseAtomicDB
from eth.rlp.blocks import BaseBlock
from eth.vm.state import BaseState
from eth.vm.base import BaseVM
from eth.vm.interrupt import (
    MissingAccountTrieNode,
    MissingBytecode,
    MissingStorageTrieNode,
)
from eth_typing import (
    Address,
    Hash32,
)
from lahja.common import BroadcastConfig

from p2p.service import BaseService

from trinity.chains.base import BaseAsyncChain
from trinity.chains.full import FullChain
from trinity.endpoint import TrinityEventBusEndpoint
from trinity.sync.common.events import (
    CollectMissingAccount,
    CollectMissingBytecode,
    CollectMissingStorage,
    DoStatelessBlockImport,
    StatelessBlockImportDone,
)

ImportBlockType = Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]


def make_pausing_beam_chain(
        vm_config: Tuple[Tuple[int, BaseVM], ...],
        chain_id: int,
        db: BaseAtomicDB,
        event_bus: TrinityEventBusEndpoint) -> FullChain:
    """
    Patch the py-evm chain with a VMState that pauses when state data
    is missing, and emits an event which requests the missing data.
    """
    pausing_vm_config = tuple(
        (starting_block, pausing_vm_decorator(vm, event_bus))
        for starting_block, vm in vm_config
    )
    PausingBeamChain = FullChain.configure(
        vm_configuration=pausing_vm_config,
        chain_id=chain_id,
    )
    return PausingBeamChain(db)


TVMFuncReturn = TypeVar('TVMFuncReturn')


def pausing_vm_decorator(
        original_vm_class: Type[BaseVM],
        event_bus: TrinityEventBusEndpoint) -> Type[BaseVM]:
    """
    Decorate a py-evm VM so that it will pause when data is missing
    """
    async def request_missing_storage(
            missing_node_hash: Hash32,
            storage_key: Hash32,
            storage_root_hash: Hash32,
            account_address: Address) -> None:
        await event_bus.request(CollectMissingStorage(
            missing_node_hash,
            storage_key,
            storage_root_hash,
            account_address,
        ))

    async def request_missing_account(
            missing_node_hash: Hash32,
            address_hash: Hash32,
            state_root_hash: Hash32) -> None:
        await event_bus.request(CollectMissingAccount(
            missing_node_hash,
            address_hash,
            state_root_hash,
        ))

    async def request_missing_bytecode(bytecode_hash: Hash32) -> None:
        await event_bus.request(CollectMissingBytecode(
            bytecode_hash,
        ))

    class PausingVMState(original_vm_class.get_state_class()):  # type: ignore
        """
        A custom version of VMState that pauses EVM execution when required data is missing.
        """

        def _pause_on_missing_data(
                self,
                unbound_vm_method: Callable[['PausingVMState', Any], TVMFuncReturn],
                *args: Any,
                **kwargs: Any) -> TVMFuncReturn:
            """
            Catch exceptions about missing state data and pause while waiting for
            the event bus to reply with the needed data.
            """
            while True:
                try:
                    return unbound_vm_method(self, *args, **kwargs)  # type: ignore
                except MissingAccountTrieNode as exc:
                    future = asyncio.run_coroutine_threadsafe(
                        request_missing_account(
                            exc.missing_node_hash,
                            exc.address_hash,
                            exc.state_root_hash,
                        ),
                        event_bus.event_loop,
                    )
                    # TODO put in a loop to truly wait forever
                    future.result(timeout=300)
                except MissingBytecode as exc:
                    future = asyncio.run_coroutine_threadsafe(
                        request_missing_bytecode(
                            exc.missing_code_hash,
                        ),
                        event_bus.event_loop,
                    )
                    # TODO put in a loop to truly wait forever
                    future.result(timeout=300)
                except MissingStorageTrieNode as exc:
                    future = asyncio.run_coroutine_threadsafe(
                        request_missing_storage(
                            exc.missing_node_hash,
                            exc.requested_key,
                            exc.storage_root_hash,
                            exc.account_address,
                        ),
                        event_bus.event_loop,
                    )
                    # TODO put in a loop to truly wait forever
                    future.result(timeout=300)

        def get_balance(self, account: bytes) -> int:
            return self._pause_on_missing_data(super().get_balance.__func__, account)

        def get_code(self, account: bytes) -> bytes:
            return self._pause_on_missing_data(super().get_code.__func__, account)

        def get_storage(self, *args: Any, **kwargs: Any) -> int:
            return self._pause_on_missing_data(super().get_storage.__func__, *args, **kwargs)

        def delete_storage(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().delete_storage.__func__, *args, **kwargs)

        def delete_account(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().delete_account.__func__, *args, **kwargs)

        def set_balance(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().set_balance.__func__, *args, **kwargs)

        def get_nonce(self, *args: Any, **kwargs: Any) -> int:
            return self._pause_on_missing_data(super().get_nonce.__func__, *args, **kwargs)

        def set_nonce(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().set_nonce.__func__, *args, **kwargs)

        def increment_nonce(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().increment_nonce.__func__, *args, **kwargs)

        def set_code(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().set_code.__func__, *args, **kwargs)

        def get_code_hash(self, *args: Any, **kwargs: Any) -> Hash32:
            return self._pause_on_missing_data(super().get_code_hash.__func__, *args, **kwargs)

        def delete_code(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().delete_code.__func__, *args, **kwargs)

        def has_code_or_nonce(self, *args: Any, **kwargs: Any) -> bool:
            return self._pause_on_missing_data(super().has_code_or_nonce.__func__, *args, **kwargs)

        def account_exists(self, *args: Any, **kwargs: Any) -> bool:
            return self._pause_on_missing_data(super().account_exists.__func__, *args, **kwargs)

        def touch_account(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().touch_account.__func__, *args, **kwargs)

        def account_is_empty(self, *args: Any, **kwargs: Any) -> bool:
            return self._pause_on_missing_data(super().account_is_empty.__func__, *args, **kwargs)

        def persist(self) -> Optional[Any]:
            return self._pause_on_missing_data(super().persist.__func__)

    class PausingVM(original_vm_class):  # type: ignore
        @classmethod
        def get_state_class(cls) -> Type[BaseState]:
            return PausingVMState

    return PausingVM


def _broadcast_import_complete(
        event_bus: TrinityEventBusEndpoint,
        block: BaseBlock,
        broadcast_config: BroadcastConfig,
        future: 'asyncio.Future[ImportBlockType]') -> None:
    completed = not future.cancelled()
    event_bus.broadcast_nowait(
        StatelessBlockImportDone(
            block,
            completed,
            future.result() if completed else None,
            future.exception() if completed else None,
        ),
        broadcast_config,
    )


class BlockImportServer(BaseService):
    def __init__(
            self,
            event_bus: TrinityEventBusEndpoint,
            beam_chain: BaseAsyncChain,
            token: CancelToken=None) -> None:
        super().__init__(token=token)
        self._event_bus = event_bus
        self._beam_chain = beam_chain

    async def _run(self) -> None:
        self.run_daemon_task(self.serve(self._event_bus, self._beam_chain))
        await self.cancellation()

    async def serve(
            self,
            event_bus: TrinityEventBusEndpoint,
            beam_chain: BaseAsyncChain) -> None:
        """
        Listen to DoStatelessBlockImport events, and import block when received.
        Reply with StatelessBlockImportDone when import is complete.
        """

        async for event in self.wait_iter(event_bus.stream(DoStatelessBlockImport)):
            # launch in new thread, so we don't block the event loop!
            import_completion = asyncio.get_event_loop().run_in_executor(
                # Maybe build the pausing chain inside the new process?
                None,
                partial(
                    beam_chain.import_block,
                    event.block,
                    perform_validation=True,
                ),
            )

            # Intentionally don't use .wait() below, because we want to hang the service from
            #   shutting down until block import is complete.
            # In the tests, for example, we await cancel() this service, so that we know
            #   that the in-progress block is complete. Then below, we do not send back
            #   the import completion (so the import server won't get triggered again).
            await import_completion

            if self.is_running:
                _broadcast_import_complete(  # type: ignore
                    event_bus,
                    event.block,
                    event.broadcast_config(),
                    import_completion,
                )
            else:
                break
