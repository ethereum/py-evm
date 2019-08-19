import asyncio
from concurrent.futures import ThreadPoolExecutor
from operator import attrgetter
from typing import (
    Any,
    Callable,
    Optional,
    Tuple,
    Type,
    TypeVar,
)

from cancel_token import CancelToken

from eth.abc import (
    AtomicDatabaseAPI,
    BlockAPI,
    BlockHeaderAPI,
    SignedTransactionAPI,
    StateAPI,
    VirtualMachineAPI,
)
from eth.vm.interrupt import (
    MissingAccountTrieNode,
    MissingBytecode,
    MissingStorageTrieNode,
)
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import (
    groupby,
)

from lahja import EndpointAPI
from lahja.common import BroadcastConfig

from p2p.service import BaseService

from trinity._utils.timer import Timer
from trinity.chains.base import AsyncChainAPI
from trinity.chains.full import FullChain
from trinity.sync.beam.constants import (
    MAX_SPECULATIVE_EXECUTIONS_PER_PROCESS,
    NUM_PREVIEW_SHARDS,
)
from trinity.sync.common.events import (
    CollectMissingAccount,
    CollectMissingBytecode,
    CollectMissingStorage,
    DoStatelessBlockImport,
    DoStatelessBlockPreview,
    MissingAccountCollected,
    MissingBytecodeCollected,
    MissingStorageCollected,
    StatelessBlockImportDone,
)

ImportBlockType = Tuple[BlockAPI, Tuple[BlockAPI, ...], Tuple[BlockAPI, ...]]


class BeamChain(FullChain):
    """
    The primary job of this patched BeamChain is to keep track of the
    first VM instance that it creates.

    Stats are attached to the VM that did the importing, and this is
    a way to get access to that particular vm instance that
    imported the block.

    My finest NFT to whoever replaces this with something better...
    """
    _first_vm = None

    def get_vm(self, header: BlockHeaderAPI) -> VirtualMachineAPI:
        vm = super().get_vm(header)
        if self._first_vm is None:
            self._first_vm = vm
        return vm

    def get_first_vm(self) -> VirtualMachineAPI:
        return self._first_vm

    def clear_first_vm(self) -> None:
        self._first_vm = None


def make_pausing_beam_chain(
        vm_config: Tuple[Tuple[int, VirtualMachineAPI], ...],
        chain_id: int,
        db: AtomicDatabaseAPI,
        event_bus: EndpointAPI,
        loop: asyncio.AbstractEventLoop,
        urgent: bool = True) -> BeamChain:
    """
    Patch the py-evm chain with a VMState that pauses when state data
    is missing, and emits an event which requests the missing data.
    """
    pausing_vm_config = tuple(
        (starting_block, pausing_vm_decorator(vm, event_bus, loop, urgent=urgent))
        for starting_block, vm in vm_config
    )
    PausingBeamChain = BeamChain.configure(
        vm_configuration=pausing_vm_config,
        chain_id=chain_id,
    )
    return PausingBeamChain(db)


TVMFuncReturn = TypeVar('TVMFuncReturn')


class BeamStats:
    num_accounts = 0
    num_account_nodes = 0
    num_bytecodes = 0
    num_storages = 0
    num_storage_nodes = 0

    # How much time is spent waiting on retrieving nodes?
    data_pause_time = 0.0

    def __str__(self) -> str:
        return (
            f"BeamStat: accts={self.num_accounts}, "
            f"a_nodes={self.num_account_nodes}, codes={self.num_bytecodes}, "
            f"strg={self.num_storages}, s_nodes={self.num_storage_nodes}, "
            f"wait={self.data_pause_time:.2f}s"
        )

    def __repr__(self) -> str:
        return (
            f"BeamStats(num_accounts={self.num_accounts}, "
            f"num_account_nodes={self.num_account_nodes}, num_bytecodes={self.num_bytecodes}, "
            f"num_storages={self.num_storages}, num_storage_nodes={self.num_storage_nodes}, "
            f"data_pause_time={self.data_pause_time:.3f}s)"
        )


def pausing_vm_decorator(
        original_vm_class: Type[VirtualMachineAPI],
        event_bus: EndpointAPI,
        loop: asyncio.AbstractEventLoop,
        urgent: bool = True) -> Type[VirtualMachineAPI]:
    """
    Decorate a py-evm VM so that it will pause when data is missing
    """
    async def request_missing_storage(
            missing_node_hash: Hash32,
            storage_key: Hash32,
            storage_root_hash: Hash32,
            account_address: Address) -> MissingStorageCollected:
        return await event_bus.request(CollectMissingStorage(
            missing_node_hash,
            storage_key,
            storage_root_hash,
            account_address,
            urgent,
        ))

    async def request_missing_account(
            missing_node_hash: Hash32,
            address_hash: Hash32,
            state_root_hash: Hash32) -> MissingAccountCollected:
        return await event_bus.request(CollectMissingAccount(
            missing_node_hash,
            address_hash,
            state_root_hash,
            urgent,
        ))

    async def request_missing_bytecode(bytecode_hash: Hash32) -> MissingBytecodeCollected:
        return await event_bus.request(CollectMissingBytecode(
            bytecode_hash,
            urgent,
        ))

    class PausingVMState(original_vm_class.get_state_class()):  # type: ignore
        """
        A custom version of VMState that pauses EVM execution when required data is missing.
        """
        stats_counter: BeamStats

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.stats_counter = BeamStats()

        def _pause_on_missing_data(
                self,
                vm_method: Callable[[Any], TVMFuncReturn],
                *args: Any,
                **kwargs: Any) -> TVMFuncReturn:
            """
            Catch exceptions about missing state data and pause while waiting for
            the event bus to reply with the needed data.
            """
            while True:
                try:
                    return vm_method(*args, **kwargs)  # type: ignore
                except MissingAccountTrieNode as exc:
                    t = Timer()
                    account_future = asyncio.run_coroutine_threadsafe(
                        request_missing_account(
                            exc.missing_node_hash,
                            exc.address_hash,
                            exc.state_root_hash,
                        ),
                        loop,
                    )
                    # TODO put in a loop to truly wait forever
                    account_event = account_future.result(timeout=300)
                    self.stats_counter.num_accounts += 1
                    self.stats_counter.num_account_nodes += account_event.num_nodes_collected
                    self.stats_counter.data_pause_time += t.elapsed
                except MissingBytecode as exc:
                    t = Timer()
                    bytecode_future = asyncio.run_coroutine_threadsafe(
                        request_missing_bytecode(
                            exc.missing_code_hash,
                        ),
                        loop,
                    )
                    # TODO put in a loop to truly wait forever
                    bytecode_future.result(timeout=300)
                    self.stats_counter.num_bytecodes += 1
                    self.stats_counter.data_pause_time += t.elapsed
                except MissingStorageTrieNode as exc:
                    t = Timer()
                    storage_future = asyncio.run_coroutine_threadsafe(
                        request_missing_storage(
                            exc.missing_node_hash,
                            exc.requested_key,
                            exc.storage_root_hash,
                            exc.account_address,
                        ),
                        loop,
                    )
                    # TODO put in a loop to truly wait forever
                    storage_event = storage_future.result(timeout=300)
                    self.stats_counter.num_storages += 1
                    self.stats_counter.num_storage_nodes += storage_event.num_nodes_collected
                    self.stats_counter.data_pause_time += t.elapsed

        def get_balance(self, account: bytes) -> int:
            return self._pause_on_missing_data(super().get_balance, account)

        def get_code(self, account: bytes) -> bytes:
            return self._pause_on_missing_data(super().get_code, account)

        def get_storage(self, *args: Any, **kwargs: Any) -> int:
            return self._pause_on_missing_data(super().get_storage, *args, **kwargs)

        def delete_storage(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().delete_storage, *args, **kwargs)

        def delete_account(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().delete_account, *args, **kwargs)

        def set_balance(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().set_balance, *args, **kwargs)

        def get_nonce(self, *args: Any, **kwargs: Any) -> int:
            return self._pause_on_missing_data(super().get_nonce, *args, **kwargs)

        def set_nonce(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().set_nonce, *args, **kwargs)

        def increment_nonce(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().increment_nonce, *args, **kwargs)

        def set_code(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().set_code, *args, **kwargs)

        def get_code_hash(self, *args: Any, **kwargs: Any) -> Hash32:
            return self._pause_on_missing_data(super().get_code_hash, *args, **kwargs)

        def delete_code(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().delete_code, *args, **kwargs)

        def has_code_or_nonce(self, *args: Any, **kwargs: Any) -> bool:
            return self._pause_on_missing_data(super().has_code_or_nonce, *args, **kwargs)

        def account_exists(self, *args: Any, **kwargs: Any) -> bool:
            return self._pause_on_missing_data(super().account_exists, *args, **kwargs)

        def touch_account(self, *args: Any, **kwargs: Any) -> None:
            return self._pause_on_missing_data(super().touch_account, *args, **kwargs)

        def account_is_empty(self, *args: Any, **kwargs: Any) -> bool:
            return self._pause_on_missing_data(super().account_is_empty, *args, **kwargs)

        def persist(self) -> Optional[Any]:
            return self._pause_on_missing_data(super().persist)

        def make_state_root(self) -> Optional[Any]:
            return self._pause_on_missing_data(super().make_state_root)

    class PausingVM(original_vm_class):  # type: ignore
        @classmethod
        def get_state_class(cls) -> Type[StateAPI]:
            return PausingVMState

        def get_beam_stats(self) -> BeamStats:
            return self.state.stats_counter

    return PausingVM


def _broadcast_import_complete(
        event_bus: EndpointAPI,
        block: BlockAPI,
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


def partial_import_block(beam_chain: AsyncChainAPI, block: BlockAPI) -> Callable[[], None]:
    """
    Get an argument-free function that will import the given block.
    """
    def _import_block() -> None:
        t = Timer()
        beam_chain.clear_first_vm()
        reorg_info = beam_chain.import_block(block, perform_validation=True)
        import_time = t.elapsed

        vm = beam_chain.get_first_vm()
        beam_stats = vm.get_beam_stats()
        beam_chain.logger.debug(
            "BeamImport %s (%d txns) total time: %.1f s, %%exec %.0f, stats: %s",
            block.header,
            len(block.transactions),
            import_time,
            100 * (import_time - beam_stats.data_pause_time) / import_time,
            vm.get_beam_stats(),
        )
        return reorg_info

    return _import_block


class BlockImportServer(BaseService):
    def __init__(
            self,
            event_bus: EndpointAPI,
            beam_chain: AsyncChainAPI,
            token: CancelToken=None) -> None:
        super().__init__(token=token)
        self._event_bus = event_bus
        self._beam_chain = beam_chain

    async def _run(self) -> None:
        self.run_daemon_task(self.serve(self._event_bus, self._beam_chain))
        await self.cancellation()

    async def serve(
            self,
            event_bus: EndpointAPI,
            beam_chain: AsyncChainAPI) -> None:
        """
        Listen to DoStatelessBlockImport events, and import block when received.
        Reply with StatelessBlockImportDone when import is complete.
        """

        async for event in self.wait_iter(event_bus.stream(DoStatelessBlockImport)):
            # launch in new thread, so we don't block the event loop!
            import_completion = self.get_event_loop().run_in_executor(
                # Maybe build the pausing chain inside the new process?
                None,
                partial_import_block(beam_chain, event.block),
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


def partial_trigger_missing_state_downloads(
        beam_chain: AsyncChainAPI,
        header: BlockHeaderAPI,
        transactions: Tuple[SignedTransactionAPI, ...]) -> Callable[[], None]:
    """
    Get an argument-free function that will trigger missing state downloads,
    by executing all the transactions, in the context of the given header.
    """
    def _trigger_missing_state_downloads() -> None:
        vm = beam_chain.get_vm(header)
        unused_header = header.copy(gas_used=0)

        # this won't actually save the results, but all we need to do is generate the trie requests
        t = Timer()
        vm.apply_all_transactions(transactions, unused_header)
        vm.state.make_state_root()
        preview_time = t.elapsed

        beam_stats = vm.get_beam_stats()
        vm.logger.debug(
            "Previewed %d transactions for %s in %.1f s, %%exec %.0f, stats: %s",
            len(transactions),
            header,
            preview_time,
            100 * (preview_time - beam_stats.data_pause_time) / preview_time,
            beam_stats,
        )

    return _trigger_missing_state_downloads


def partial_speculative_execute(
        beam_chain: AsyncChainAPI,
        header: BlockHeaderAPI,
        transactions: Tuple[SignedTransactionAPI, ...]) -> Callable[[], None]:
    """
    Get an argument-free function that will trigger missing state downloads,
    by executing all the transactions, in the context of the given header.
    """
    def _trigger_missing_state_downloads() -> None:
        vm = beam_chain.get_vm(header)
        unused_header = header.copy(gas_used=0)

        # this won't actually save the results, but all we need to do is generate the trie requests
        t = Timer()
        try:
            _, receipts, _ = vm.apply_all_transactions(transactions, unused_header)
        except ValidationError as exc:
            preview_time = t.elapsed
            vm.logger.debug(
                "Speculative transactions %d failed for %s after %.1fs: %s",
                transactions,
                header,
                preview_time,
                exc,
            )
        else:
            preview_time = t.elapsed

            beam_stats = vm.get_beam_stats()
            vm.logger.debug2(
                "Speculative transaction (%d/%d gas) for %s in %.1f s, %%exec %.0f, stats: %s",
                sum(r.gas_used for r in receipts),
                sum(txn.gas for txn in transactions),
                header,
                preview_time,
                100 * (preview_time - beam_stats.data_pause_time) / preview_time,
                beam_stats,
            )

    return _trigger_missing_state_downloads


class BlockPreviewServer(BaseService):
    def __init__(
            self,
            event_bus: EndpointAPI,
            beam_chain: AsyncChainAPI,
            shard_num: int,
            token: CancelToken=None) -> None:
        super().__init__(token=token)
        self._event_bus = event_bus
        self._beam_chain = beam_chain

        if shard_num < 0 or shard_num >= NUM_PREVIEW_SHARDS:
            raise ValidationError(
                f"Can only run up to {NUM_PREVIEW_SHARDS}, tried to run {shard_num}"
            )
        else:
            self._shard_num = shard_num

    async def _run(self) -> None:
        self.run_daemon_task(self.serve(self._event_bus, self._beam_chain))
        await self.cancellation()

    async def serve(
            self,
            event_bus: EndpointAPI,
            beam_chain: AsyncChainAPI) -> None:
        """
        Listen to DoStatelessBlockPreview events, and execute the transactions to prefill
        all the needed state data.
        """
        speculative_thread_executor = ThreadPoolExecutor(
            max_workers=MAX_SPECULATIVE_EXECUTIONS_PER_PROCESS,
            thread_name_prefix="trinity-spec-exec-",
        )

        async for event in self.wait_iter(event_bus.stream(DoStatelessBlockPreview)):
            if event.header.block_number % NUM_PREVIEW_SHARDS != self._shard_num:
                continue

            self.logger.debug(
                "DoStatelessBlockPreview-%d is previewing new block: %s",
                self._shard_num,
                event.header,
            )
            # Parallel Execution:
            # Run a complete block end-to-end
            asyncio.get_event_loop().run_in_executor(
                # Maybe build the pausing chain inside the new process, so we can use process pool?
                None,
                partial_trigger_missing_state_downloads(
                    beam_chain,
                    event.header,
                    event.transactions,
                )
            )

            # Speculative Execution:
            # Split transactions into groups by sender, and run them independently.
            # This effectively assumes that the transactions by each sender are not
            #   affected by any other transactions in the block. This is often true,
            #   so it helps speed up the search for data.
            # Being able to retrieve this predicted data in parallel, asking for more
            # trie nodes in each GetNodeData request, can help make the difference
            # between keeping up and falling behind, on the network.
            transaction_groups = groupby(attrgetter('sender'), event.transactions)
            for sender_transactions in transaction_groups.values():
                asyncio.get_event_loop().run_in_executor(
                    speculative_thread_executor,
                    partial_speculative_execute(
                        beam_chain,
                        event.header,
                        sender_transactions,
                    )
                )
            # we don't need to broadcast that the preview is complete, so immediately
            # look for next preview request. That way, we can run them in parallel.
