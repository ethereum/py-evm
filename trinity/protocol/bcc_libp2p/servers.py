import asyncio
from typing import (
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Set,
    Tuple,
    Union,
)

from cancel_token import (
    CancelToken,
)
from eth.exceptions import (
    BlockNotFound,
)
from eth_utils import (
    ValidationError,
    encode_hex,
    to_tuple,
)

import ssz

from libp2p.pubsub.pb import rpc_pb2

from p2p.service import BaseService

from eth2.beacon.chains.base import (
    BaseBeaconChain,
)
from eth2.beacon.operations.attestation_pool import AttestationPool
from eth2.beacon.types.attestations import (
    Attestation,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)
from eth2.beacon.typing import (
    SigningRoot,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_attestation_slot,
)
from eth2.beacon.typing import Slot

from trinity.protocol.bcc_libp2p.node import Node

from .configs import (
    PUBSUB_TOPIC_BEACON_BLOCK,
    PUBSUB_TOPIC_BEACON_ATTESTATION,
)

PROCESS_ORPHAN_BLOCKS_PERIOD = 10.0


class OrphanBlockPool:
    """
    Store the orphan blocks(the blocks who arrive before their parents).
    """
    # TODO: can probably use lru-cache or even database
    _pool: Set[BaseBeaconBlock]

    def __init__(self) -> None:
        self._pool = set()

    def __len__(self) -> int:
        return len(self._pool)

    def __contains__(self, block_or_block_root: Union[BaseBeaconBlock, SigningRoot]) -> bool:
        block_root: SigningRoot
        if isinstance(block_or_block_root, BaseBeaconBlock):
            block_root = block_or_block_root.signing_root
        elif isinstance(block_or_block_root, bytes):
            block_root = block_or_block_root
        else:
            raise TypeError("`block_or_block_root` should be `BaseBeaconBlock` or `SigningRoot`")
        try:
            self.get(block_root)
            return True
        except BlockNotFound:
            return False

    def to_list(self) -> List[BaseBeaconBlock]:
        return list(self._pool)

    def get(self, block_root: SigningRoot) -> BaseBeaconBlock:
        for block in self._pool:
            if block.signing_root == block_root:
                return block
        raise BlockNotFound(f"No block with signing_root {block_root.hex()} is found")

    def add(self, block: BaseBeaconBlock) -> None:
        if block in self._pool:
            return
        self._pool.add(block)

    def pop_children(self, block_root: SigningRoot) -> Tuple[BaseBeaconBlock, ...]:
        children = tuple(
            orphan_block
            for orphan_block in self._pool
            if orphan_block.parent_root == block_root
        )
        self._pool.difference_update(children)
        return children


class BCCReceiveServer(BaseService):

    chain: BaseBeaconChain
    p2p_node: Node
    topic_msg_queues: Dict[str, 'asyncio.Queue[rpc_pb2.Message]']
    attestation_pool: AttestationPool
    orphan_block_pool: OrphanBlockPool

    def __init__(
            self,
            chain: BaseBeaconChain,
            p2p_node: Node,
            topic_msg_queues: Dict[str, 'asyncio.Queue[rpc_pb2.Message]'],
            cancel_token: CancelToken = None) -> None:
        super().__init__(cancel_token)
        self.chain = chain
        self.topic_msg_queues = topic_msg_queues
        self.p2p_node = p2p_node
        self.attestation_pool = AttestationPool()
        self.orphan_block_pool = OrphanBlockPool()
        self.ready = asyncio.Event()

    async def _run(self) -> None:
        while not self.p2p_node.is_started:
            await self.sleep(0.5)
        self.logger.info("BCCReceiveServer up")
        self.run_daemon_task(self._handle_beacon_attestation_loop())
        self.run_daemon_task(self._handle_beacon_block_loop())
        self.run_daemon_task(self._process_orphan_blocks_loop())
        self.ready.set()
        await self.cancellation()

    async def _handle_message(
            self,
            topic: str,
            handler: Callable[[rpc_pb2.Message], Awaitable[None]]) -> None:
        queue = self.topic_msg_queues[topic]
        while True:
            message = await queue.get()
            # Libp2p let the sender receive their own message, which we need to ignore here.
            if message.from_id == self.p2p_node.peer_id:
                queue.task_done()
                continue
            else:
                await handler(message)
                queue.task_done()

    async def _handle_beacon_attestation_loop(self) -> None:
        await self._handle_message(
            PUBSUB_TOPIC_BEACON_ATTESTATION,
            self._handle_beacon_attestations
        )

    async def _handle_beacon_block_loop(self) -> None:
        await self._handle_message(
            PUBSUB_TOPIC_BEACON_BLOCK,
            self._handle_beacon_block
        )

    async def _process_orphan_blocks_loop(self) -> None:
        """
        Periodically requesting for parent blocks of the
        orphan blocks in the orphan block pool.
        """
        while True:
            await self.sleep(PROCESS_ORPHAN_BLOCKS_PERIOD)
            if len(self.orphan_block_pool) == 0:
                continue
            # TODO: Prune Bruce Wayne type of orphan block
            # (whose parent block seemingly never going to show up)
            orphan_blocks = self.orphan_block_pool.to_list()
            parent_roots = set(block.parent_root for block in orphan_blocks)
            block_roots = set(block.signing_root for block in orphan_blocks)
            # Remove dependent orphan blocks
            parent_roots.difference_update(block_roots)
            # Keep requesting parent blocks from all peers
            for peer in self.p2p_node.handshaked_peers.peers.values():
                if len(parent_roots) == 0:
                    break
                blocks = await peer.request_beacon_blocks_by_root(
                    tuple(parent_roots)
                )
                for block in blocks:
                    try:
                        parent_roots.remove(block.signing_root)
                    except ValueError:
                        self.logger.debug(
                            "peer=%s sent incorrect block=%s",
                            peer._id,
                            encode_hex(block.signing_root),
                        )
                        # This should not happen if peers are returning correct blocks
                        continue
                    else:
                        self._process_received_block(block)

    async def _handle_beacon_attestations(self, msg: rpc_pb2.Message) -> None:
        attestation = ssz.decode(msg.data, sedes=Attestation)

        self.logger.debug("Received attestation=%s", attestation)

        # Check if attestation has been seen already.
        if not self._is_attestation_new(attestation):
            return
        # Add new attestation to attestation pool.
        self.attestation_pool.add(attestation)

    async def _handle_beacon_block(self, msg: rpc_pb2.Message) -> None:
        block = ssz.decode(msg.data, BeaconBlock)
        self._process_received_block(block)

    def _is_attestation_new(self, attestation: Attestation) -> bool:
        """
        Check if the attestation is already in the database or the attestion pool.
        """
        if attestation.hash_tree_root in self.attestation_pool:
            return False
        return not self.chain.attestation_exists(attestation.hash_tree_root)

    def _process_received_block(self, block: BaseBeaconBlock) -> None:
        # If the block is an orphan, put it to the orphan pool
        self.logger.debug(
            'Received block over gossip. slot=%d signing_root=%s',
            block.slot,
            block.signing_root.hex(),
        )
        if not self._is_block_root_in_db(block.parent_root):
            if block not in self.orphan_block_pool:
                self.logger.debug("Found orphan_block=%s", block)
                self.orphan_block_pool.add(block)
            return
        try:
            self.chain.import_block(block)
            self.logger.info(
                "Successfully imported block=%s",
                encode_hex(block.signing_root),
            )
        # If the block is invalid, we should drop it.
        except ValidationError as error:
            # TODO: Possibly drop all of its descendants in `self.orphan_block_pool`?
            self.logger.debug("Fail to import block=%s  reason=%s", block, error)
        else:
            # Successfully imported the block. See if any blocks in `self.orphan_block_pool`
            # depend on it. If there are, try to import them.
            # TODO: should be done asynchronously?
            self._try_import_orphan_blocks(block.signing_root)
            # Remove attestations in block that are also in the attestation pool.
            self.attestation_pool.batch_remove(block.body.attestations)

    def _try_import_orphan_blocks(self, parent_root: SigningRoot) -> None:
        """
        Perform ``chain.import`` on the blocks in ``self.orphan_block_pool`` in breadth-first
        order, starting from the children of ``parent_root``.
        """
        imported_roots: List[SigningRoot] = []

        imported_roots.append(parent_root)
        while len(imported_roots) != 0:
            current_parent_root = imported_roots.pop()
            # Only process the children if the `current_parent_root` is already in db.
            if not self._is_block_root_in_db(block_root=current_parent_root):
                continue
            # If succeeded, handle the orphan blocks which depend on this block.
            children = self.orphan_block_pool.pop_children(current_parent_root)
            if len(children) > 0:
                self.logger.debug(
                    "Blocks=%s match their parent block, parent_root=%s",
                    children,
                    encode_hex(current_parent_root),
                )
            for block in children:
                try:
                    self.chain.import_block(block)
                    self.logger.info(
                        "Successfully imported block=%s",
                        encode_hex(block.signing_root),
                    )
                    imported_roots.append(block.signing_root)
                except ValidationError as error:
                    # TODO: Possibly drop all of its descendants in `self.orphan_block_pool`?
                    self.logger.debug("Fail to import block=%s  reason=%s", block, error)

    def _is_block_root_in_orphan_block_pool(self, block_root: SigningRoot) -> bool:
        return block_root in self.orphan_block_pool

    def _is_block_root_in_db(self, block_root: SigningRoot) -> bool:
        try:
            self.chain.get_block_by_root(block_root=block_root)
            return True
        except BlockNotFound:
            return False

    def _is_block_root_seen(self, block_root: SigningRoot) -> bool:
        if self._is_block_root_in_orphan_block_pool(block_root=block_root):
            return True
        return self._is_block_root_in_db(block_root=block_root)

    def _is_block_seen(self, block: BaseBeaconBlock) -> bool:
        return self._is_block_root_seen(block_root=block.signing_root)

    @to_tuple
    def get_ready_attestations(self, current_slot: Slot) -> Iterable[Attestation]:
        config = self.chain.get_state_machine().config
        for attestation in self.attestation_pool.get_all():
            try:
                validate_attestation_slot(
                    attestation.data.slot,
                    current_slot,
                    config.SLOTS_PER_EPOCH,
                    config.MIN_ATTESTATION_INCLUSION_DELAY,
                )
            except ValidationError:
                continue
            else:
                yield attestation
