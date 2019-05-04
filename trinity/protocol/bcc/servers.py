from typing import (
    cast,
    AsyncIterator,
    Dict,
    FrozenSet,
    List,
    Set,
    Tuple,
    Type,
)

from eth_typing import (
    Hash32,
)

from eth_utils import (
    ValidationError,
)

from cancel_token import CancelToken

import ssz

from p2p import protocol
from p2p.peer import (
    BasePeer,
)
from p2p.protocol import Command

from eth.exceptions import (
    BlockNotFound,
    ParentNotFound,
)

from eth2.beacon.chains.base import BaseBeaconChain

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
from trinity._utils.les import (
    gen_request_id,
)
from trinity.db.beacon.chain import BaseAsyncBeaconChainDB
from trinity.protocol.common.servers import BaseRequestServer
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


class OrphanBlockPool:
    # TODO: can probably use lru-cache or even database
    _pool: Set[BaseBeaconBlock]

    def __init__(self) -> None:
        self._pool = set()

    def get(self, block_root: Hash32) -> BaseBeaconBlock:
        for block in self._pool:
            if block.signing_root == block_root:
                return block
        raise BlockNotFound(f"No block with signing_root {block_root} is found")

    def add(self, block: BaseBeaconBlock) -> None:
        if block in self._pool:
            return
        self._pool.add(block)

    def pop_children(self, block_root: BaseBeaconBlock) -> Tuple[BaseBeaconBlock, ...]:
        children = tuple(
            orphan_block
            for orphan_block in self._pool
            if orphan_block.previous_block_root == block_root
        )
        self._pool.difference_update(children)
        return children


class BCCReceiveServer(BaseReceiveServer):
    subscription_msg_types: FrozenSet[Type[Command]] = frozenset({
        BeaconBlocks,
        NewBeaconBlock,
    })

    map_request_id_block_root: Dict[int, Hash32]
    orphan_block_pool: OrphanBlockPool

    def __init__(
            self,
            chain: BaseBeaconChain,
            peer_pool: BCCPeerPool,
            token: CancelToken = None) -> None:
        super().__init__(peer_pool, token)
        self.chain = chain
        self.map_request_id_block_root = {}
        self.orphan_block_pool = OrphanBlockPool()

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

    async def _handle_beacon_blocks(self, peer: BCCPeer, msg: BeaconBlocksMessage) -> None:
        if not peer.is_operational:
            return
        request_id = msg["request_id"]
        if request_id not in self.map_request_id_block_root:
            raise Exception(f"request_id={request_id} is not found")
        encoded_blocks = msg["encoded_blocks"]
        # TODO: remove this condition check in the future, when we start requesting more than one
        #   block at a time.
        if len(encoded_blocks) != 1:
            raise Exception("should only receive 1 block from our requests")
        block = ssz.decode(encoded_blocks[0], BeaconBlock)
        if block.signing_root != self.map_request_id_block_root[request_id]:
            raise Exception(
                f"block signing_root {block.signing_root} does not correpond to"
                "the one we requested"
            )
        self.logger.debug(f"received request_id={request_id}, block={block}")
        self._process_received_block(block)
        del self.map_request_id_block_root[request_id]

    async def _handle_new_beacon_block(self, peer: BCCPeer, msg: NewBeaconBlockMessage) -> None:
        if not peer.is_operational:
            return
        encoded_block = msg["encoded_block"]
        block = ssz.decode(encoded_block, BeaconBlock)
        if self._is_block_seen(block):
            raise Exception(f"block {block} is seen before")
        self.logger.debug(f"received block={block}")
        # TODO: check the proposer signature before importing the block
        if self._process_received_block(block):
            self._broadcast_block(block, from_peer=peer)

    def _process_received_block(self, block: BaseBeaconBlock) -> bool:
        try:
            self._import_block(block)
        except ParentNotFound:
            self.logger.debug(f"found orphan block={block}")
            self.orphan_block_pool.add(block)
            self._request_block_by_root(block_root=block.previous_block_root)
            return False
        except ValidationError:
            # TODO: Possibly drop all of its descendants in `self.orphan_block_pool`?
            return False
        except Exception:
            # Unexpected result
            raise
        else:
            # Successfully imported the block. See if anyone in `self.orphan_block_pool` which
            # depends on it. If there are, try to import them.
            self._try_import_orphan_blocks(block.signing_root)
            return True

    def _try_import_orphan_blocks(self, parent_root: BeaconBlock) -> None:
        imported_roots: List[BeaconBlock] = []

        imported_roots.append(parent_root)
        while len(imported_roots) != 0:
            current_parent_root = imported_roots.pop()
            # Only process the children if the `parent_root` is already in db.
            if not self._is_block_root_in_db(block_root=parent_root):
                continue
            # If succeeded, handle the orphan blocks which depend on this block.
            children = self.orphan_block_pool.pop_children(current_parent_root)
            if len(children) > 0:
                self.logger.debug(
                    f"blocks {children} match their parent block, block.root={current_parent_root}"
                )
            for block in children:
                self.logger.debug(f"try to import block={block}")
                try:
                    self.chain.import_block(block)
                    self.logger.debug(f"successfully imported block={block}")
                    imported_roots.append(block.signing_root)
                except ValidationError:
                    # If enter here, it means we fail to import the block due to the reason other
                    # than the missing parent. Currently, just implicitly drop it.
                    pass

    def _request_block_by_root(self, block_root: Hash32) -> None:
        for peer in self._peer_pool.connected_nodes.values():
            peer = cast(BCCPeer, peer)
            request_id = gen_request_id()
            self.logger.debug(
                bold_red(f"send block request to: request_id={request_id}, peer={peer}")
            )
            self.map_request_id_block_root[request_id] = block_root
            peer.sub_proto.send_get_blocks(
                block_root,
                max_blocks=1,
                request_id=request_id,
            )

    def _broadcast_block(self, block: BaseBeaconBlock, from_peer: BCCPeer = None) -> None:
        for peer in self._peer_pool.connected_nodes.values():
            peer = cast(BCCPeer, peer)
            # skip the peer who send the block to use
            if from_peer is not None and peer == from_peer:
                continue
            request_id = gen_request_id()
            self.logger.debug(
                bold_red(f"send block request to: request_id={request_id}, peer={peer}")
            )
            peer.sub_proto.send_new_block(block=block)

    def _import_block(self, block: BaseBeaconBlock):
        if not self._is_block_root_in_db(block.previous_block_root):
            raise ParentNotFound
        self.chain.import_block(block)

    def _is_block_root_in_orphan_block_pool(self, block_root: Hash32) -> bool:
        try:
            self.orphan_block_pool.get(block_root=block_root)
            return True
        except BlockNotFound:
            return False

    def _is_block_root_in_db(self, block_root: Hash32) -> bool:
        try:
            self.chain.get_block_by_root(block_root=block_root)
            return True
        except BlockNotFound:
            return False

    def _is_block_root_seen(self, block_root: Hash32) -> bool:
        if self._is_block_root_in_orphan_block_pool(block_root=block_root):
            return True
        return self._is_block_root_in_db(block_root=block_root)

    def _is_block_seen(self, block: BaseBeaconBlock) -> bool:
        return self._is_block_root_seen(block_root=block.signing_root)
