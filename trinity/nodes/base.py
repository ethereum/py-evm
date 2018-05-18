from abc import abstractmethod
import asyncio
from pathlib import PurePath
from threading import Thread
from typing import Type

from evm.chains.base import BaseChain
from evm.db.header import BaseHeaderDB
from p2p.service import (
    BaseService,
    EmptyService,
)
from trinity.rpc.main import (
    RPCServer,
)
from trinity.rpc.ipc import (
    IPCServer,
)


class Node(BaseService):
    """
    Create usable nodes by adding subclasses that define the following
    unset attributes...
    """

    chain_class: Type[BaseChain] = None
    peer_chain_class: Type[BaseService] = None

    def __init__(
            self,
            headerdb: BaseHeaderDB,
            peer_pool,
            jsonrpc_ipc_path: PurePath = None):
        super().__init__()
        self._headerdb = headerdb
        self._jsonrpc_ipc_path = jsonrpc_ipc_path
        self._peer_pool = peer_pool
        self._peer_chain = self.peer_chain_class(headerdb, peer_pool)

    @abstractmethod
    def get_chain(self) -> BaseChain:
        raise NotImplementedError("Node classes must implement this method")

    def make_ipc_server(self) -> IPCServer:
        if self._jsonrpc_ipc_path:
            rpc = RPCServer(self.get_chain())
            return IPCServer(rpc, self._jsonrpc_ipc_path)
        else:
            return EmptyService()

    async def _run(self):
        ipc_server = self.make_ipc_server()

        # The RPC server needs its own thread, because it provides a synchcronous
        # API which might call into p2p async methods. These sync->async calls
        # deadlock if they are run in the same Thread and loop.
        ipc_loop = self._make_new_loop_thread()

        # keep a copy on self, for debugging
        self._ipc_server, self._ipc_loop = ipc_server, ipc_loop

        try:
            asyncio.ensure_future(self._peer_pool.run())
            asyncio.run_coroutine_threadsafe(ipc_server.run(), loop=ipc_loop)
            await self._peer_chain.run()
        finally:
            await ipc_server.stop()
            await self._peer_pool.cancel()

    async def _cleanup(self):
        await self._peer_chain.stop()

    def _make_new_loop_thread(self):
        new_loop = asyncio.new_event_loop()

        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = Thread(target=start_loop, args=(new_loop, ))
        thread.start()

        return new_loop
