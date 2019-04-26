from abc import abstractmethod
import random
from typing import (
    cast,
    AsyncIterator,
    FrozenSet,
    MutableSet,
    List,
    Type,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    ValidationError,
)

from cancel_token import CancelToken, OperationCancelled

import ssz

from p2p import protocol
from p2p.peer import (
    BasePeer,
    PeerSubscriber,
)
from p2p.protocol import Command
from p2p.service import BaseService

from eth.exceptions import BlockNotFound

from eth2.beacon.chains.base import BeaconChain

from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)
from eth2.beacon.typing import (
    Slot,
)

from trinity._utils.shellart import (
    bold_red,
)
from trinity.db.beacon.chain import BaseAsyncBeaconChainDB
from trinity.protocol.common.servers import BaseRequestServer
from trinity.protocol.common.peer import BasePeerPool
from trinity.protocol.bcc.commands import (
    BeaconBlocks,
    BeaconBlocksMessage,
    GetBeaconBlocks,
    GetBeaconBlocksMessage,
    NewBeaconBlock,
    NewBeaconBlockMessage,
)
from trinity.protocol.bcc.peer import (
    BCCPeer,
    BCCPeerPool,
)


class BCCRequestServer(BaseRequestServer):
    subscription_msg_types: FrozenSet[Type[Command]] = frozenset({
        GetBeaconBlocks,
    })

    def __init__(self,
                 db: BaseAsyncBeaconChainDB,
                 peer_pool: BCCPeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(peer_pool, token)
        self.db = db

    async def _handle_msg(self, base_peer: BasePeer, cmd: Command,
                          msg: protocol._DecodedMsgType) -> None:
        peer = cast(BCCPeer, base_peer)
        self.logger.debug("cmd %s" % cmd)
        if isinstance(cmd, GetBeaconBlocks):
            await self._handle_get_beacon_blocks(peer, cast(GetBeaconBlocksMessage, msg))
        else:
            raise Exception(f"Invariant: Only subscribed to {self.subscription_msg_types}")

    async def _handle_get_beacon_blocks(self, peer: BCCPeer, msg: GetBeaconBlocksMessage) -> None:
        if not peer.is_operational:
            return

        request_id = msg["request_id"]
        max_blocks = msg["max_blocks"]
        block_slot_or_root = msg["block_slot_or_root"]

        try:
            if isinstance(block_slot_or_root, int):
                # TODO: pass accurate `block_class: Type[BaseBeaconBlock]` under
                # per BeaconStateMachine fork
                start_block = await self.db.coro_get_canonical_block_by_slot(
                    Slot(block_slot_or_root),
                    BeaconBlock,
                )
            elif isinstance(block_slot_or_root, bytes):
                # TODO: pass accurate `block_class: Type[BaseBeaconBlock]` under
                # per BeaconStateMachine fork
                start_block = await self.db.coro_get_block_by_root(
                    Hash32(block_slot_or_root),
                    BeaconBlock,
                )
            else:
                raise TypeError(
                    f"Invariant: unexpected type for 'block_slot_or_root': "
                    f"{type(block_slot_or_root)}"
                )
        except BlockNotFound:
            start_block = None

        if start_block is not None:
            self.logger.debug2(
                "%s requested %d blocks starting with %s",
                peer,
                max_blocks,
                start_block,
            )
            blocks = tuple([b async for b in self._get_blocks(start_block, max_blocks)])

        else:
            self.logger.debug2("%s requested unknown block %s", block_slot_or_root)
            blocks = ()

        self.logger.debug2("Replying to %s with %d blocks", peer, len(blocks))
        peer.sub_proto.send_blocks(blocks, request_id)

    async def _get_blocks(self,
                          start_block: BaseBeaconBlock,
                          max_blocks: int) -> AsyncIterator[BaseBeaconBlock]:
        if max_blocks < 0:
            raise Exception("Invariant: max blocks cannot be negative")

        if max_blocks == 0:
            return

        yield start_block

        try:
            # ensure only a connected chain is returned (breaks might occur if the start block is
            # not part of the canonical chain or if the canonical chain changes during execution)
            start = start_block.slot + 1
            end = start + max_blocks - 1
            parent = start_block
            for slot in range(start, end):
                # TODO: pass accurate `block_class: Type[BaseBeaconBlock]` under
                # per BeaconStateMachine fork
                block = await self.db.coro_get_canonical_block_by_slot(slot, BeaconBlock)
                if block.previous_block_root == parent.signing_root:
                    yield block
                else:
                    break
                parent = block
        except BlockNotFound:
            return


# FIXME: `BaseReceiveServer` is the same as `BaseRequestServer`.
# Since it's not settled that a `BaseReceiveServer` is needed and so
# in order not to pollute /trinity/protocol/common/servers.py,
# add the `BaseReceiveServer` here instead.
class BaseReceiveServer(BaseRequestServer):
    pass


class BCCReceiveServer(BaseReceiveServer):
    subscription_msg_types: FrozenSet[Type[Command]] = frozenset({
        BeaconBlocks,
        NewBeaconBlock,
    })

    requested_ids: MutableSet[int]
    # TODO: probably use lru-cache or other cache in the future?
    #   map from `block.parent_root` to `block`
    orphan_block_pool: List[BeaconBlock]

    def __init__(
            self,
            chain: BeaconChain,
            peer_pool: BCCPeerPool,
            token: CancelToken = None) -> None:
        super().__init__(peer_pool, token)
        self.chain = chain
        self.orphan_block_pool = []
        self.requested_ids = set()

    async def _handle_msg(self, base_peer: BasePeer, cmd: Command,
                          msg: protocol._DecodedMsgType) -> None:
        peer = cast(BCCPeer, base_peer)
        self.logger.debug("cmd %s" % cmd)
        if isinstance(cmd, NewBeaconBlock):
            await self._handle_new_beacon_block(peer, cast(NewBeaconBlockMessage, msg))
        elif isinstance(cmd, BeaconBlocks):
            await self._handle_beacon_blocks(peer, cast(BeaconBlocksMessage, msg))
        else:
            raise Exception(f"Invariant: Only subscribed to {self.subscription_msg_types}")

    async def _handle_beacon_blocks(self, peer: BCCPeer, msg: NewBeaconBlockMessage) -> None:
        if not peer.is_operational:
            return
        request_id = msg["request_id"]
        if request_id not in self.requested_ids:
            return
        encoded_blocks = msg["encoded_blocks"]
        if len(encoded_blocks) != 1:
            raise Exception("should only receive 1 block from our requests")
        resp_block = ssz.decode(encoded_blocks[0], BeaconBlock)
        self.logger.debug(f"received request_id={request_id}, resp_block={resp_block}")  # noqa: E501
        self._try_import_or_handle_orphan(resp_block)
        self.requested_ids.remove(request_id)

    async def _handle_new_beacon_block(self, peer: BCCPeer, msg: NewBeaconBlockMessage) -> None:
        if not peer.is_operational:
            return
        encoded_block = msg["encoded_block"]
        # TODO: Catch ssz decode error.
        block = ssz.decode(encoded_block, BeaconBlock)
        self.logger.debug(f"received block={block}")  # noqa: E501
        self._try_import_or_handle_orphan(block)

    def _try_import_or_handle_orphan(self, block: BeaconBlock) -> None:
        blocks_to_be_imported: List[BeaconBlock] = []
        blocks_failed_to_be_imported: List[BeaconBlock] = []

        blocks_to_be_imported.append(block)
        while len(blocks_to_be_imported) != 0:
            block = blocks_to_be_imported.pop()
            # try to import the block
            try:
                self.logger.debug(f"try to import block={block}")
                self.chain.import_block(block)
                self.logger.debug(f"successfully imported block={block}")
            except ValidationError:
                self.logger.debug(f"failed to import block={block}, add to the orphan pool")
                # if failed, add the block and the rest of the queue back to the pool
                blocks_failed_to_be_imported.append(block)
                #   and send request for their parents
                self._request_block_by_root(block_root=block.parent_root)
            # if succeeded, handle the orphan blocks which depend on this block.
            matched_orphan_blocks = tuple(
                orphan_block
                for orphan_block in self.orphan_block_pool
                if orphan_block.parent_root == block.root
            )
            if len(matched_orphan_blocks) > 0:
                self.logger.debug(
                    f"blocks {matched_orphan_blocks} match their parent {block}"
                )
                blocks_to_be_imported.extend(matched_orphan_blocks)
                self.orphan_block_pool = list(
                    set(self.orphan_block_pool).difference(matched_orphan_blocks)
                )
        # add the failed-to-be-imported blocks back
        self.orphan_block_pool.extend(blocks_failed_to_be_imported)

    def _request_block_by_root(self, block_root: Hash32) -> None:
        for i, peer in enumerate(self._peer_pool.connected_nodes.values()):
            self.logger.debug(
                bold_red(f"send block request to: request_id={i}, peer={peer}")
            )
            req_request_id = random.randint(0, 32768)
            self.requested_ids.add(req_request_id)
            peer.sub_proto.send_get_blocks(
                block_root,
                max_blocks=1,
                request_id=req_request_id,
            )
