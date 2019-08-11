import asyncio
from typing import (
    Dict,
    Iterable,
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
from eth_typing import (
    Hash32,
)
from eth_utils import (
    ValidationError,
    encode_hex,
    to_tuple,
)

import ssz

from libp2p.pubsub.pb import rpc_pb2

from p2p.service import BaseService

from eth2.beacon.attestation_helpers import (
    get_attestation_data_slot,
)
from eth2.beacon.chains.base import (
    BaseBeaconChain,
)
from eth2.beacon.types.attestations import (
    Attestation,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_attestation_slot,
)

from trinity.exceptions import (
    AttestationNotFound,
)

from .configs import (
    PUBSUB_TOPIC_BEACON_BLOCK,
    PUBSUB_TOPIC_BEACON_ATTESTATION,
    SSZ_MAX_LIST_SIZE,
)


class AttestationPool:
    """
    Stores the attestations not yet included on chain.
    """
    # TODO: can probably use lru-cache or even database
    _pool: Set[Attestation]

    def __init__(self) -> None:
        self._pool = set()

    def __contains__(self, attestation_or_root: Union[Attestation, Hash32]) -> bool:
        attestation_root: Hash32
        if isinstance(attestation_or_root, Attestation):
            attestation_root = attestation_or_root.hash_tree_root
        elif isinstance(attestation_or_root, bytes):
            attestation_root = attestation_or_root
        else:
            raise TypeError(
                f"`attestation_or_root` should be `Attestation` or `Hash32`,"
                f" got {type(attestation_or_root)}"
            )
        try:
            self.get(attestation_root)
            return True
        except AttestationNotFound:
            return False

    def get(self, attestation_root: Hash32) -> Attestation:
        for attestation in self._pool:
            if attestation.hash_tree_root == attestation_root:
                return attestation
        raise AttestationNotFound(
            f"No attestation with root {encode_hex(attestation_root)} is found.")

    def get_all(self) -> Tuple[Attestation, ...]:
        return tuple(self._pool)

    def add(self, attestation: Attestation) -> None:
        if attestation not in self._pool:
            self._pool.add(attestation)

    def batch_add(self, attestations: Iterable[Attestation]) -> None:
        self._pool = self._pool.union(set(attestations))

    def remove(self, attestation: Attestation) -> None:
        if attestation in self._pool:
            self._pool.remove(attestation)

    def batch_remove(self, attestations: Iterable[Attestation]) -> None:
        self._pool.difference_update(attestations)


class BCCReceiveServer(BaseService):

    chain: BaseBeaconChain
    topic_msg_queues: Dict[str, "asyncio.Queue[rpc_pb2.Message]"]
    attestation_pool: AttestationPool
    # TODO: Add orphan block pool and request parent block function back
    # after RPC for requesting beacon block is built

    def __init__(
            self,
            chain: BaseBeaconChain,
            topic_msg_queues: Dict[str, asyncio.Queue],
            cancel_token: CancelToken = None) -> None:
        super().__init__(cancel_token)
        self.chain = chain
        self.topic_msg_queues = topic_msg_queues
        self.attestation_pool = AttestationPool()

    async def _run(self) -> None:
        self.logger.info(f"BCCReceiveServer up")
        self.run_daemon_task(self._handle_beacon_attestation_loop())
        self.run_daemon_task(self._handle_beacon_block_loop())
        await self.cancellation()

    async def _handle_beacon_attestation_loop(self) -> None:
        while True:
            msg = await self.topic_msg_queues[PUBSUB_TOPIC_BEACON_ATTESTATION].get()
            await self._handle_attestations(msg)

    async def _handle_beacon_block_loop(self) -> None:
        while True:
            msg = await self.topic_msg_queues[PUBSUB_TOPIC_BEACON_BLOCK].get()
            await self._handle_beacon_block(msg)

    async def _handle_attestations(self, msg: rpc_pb2.Message) -> None:
        attestations = ssz.decode(msg.data, sedes=ssz.List(Attestation, SSZ_MAX_LIST_SIZE))

        self.logger.debug("Received attestations=%s", attestations)

        # Check if attestations has been seen already.
        # Filter out those seen already.
        new_attestations = tuple(
            filter(
                self._is_attestation_new,
                attestations,
            )
        )
        if len(new_attestations) == 0:
            return
        # Add new attestations to attestation pool.
        self.attestation_pool.batch_add(new_attestations)

    async def _handle_beacon_block(self, msg: rpc_pb2.Message) -> None:
        block = ssz.decode(msg.data, BeaconBlock)
        if self._is_block_seen(block):
            return
        self.logger.debug("Received new block=%s", block)

        try:
            self.chain.import_block(block)
        # If the block is invalid, we should drop it.
        except ValidationError:
            return
        except Exception:
            # Unexpected result
            return
        else:
            # Remove attestations in block that are also in the attestation pool.
            self.attestation_pool.batch_remove(block.body.attestations)

    def _is_attestation_new(self, attestation: Attestation) -> bool:
        """
        Check if the attestation is already in the database or the attestion pool.
        """
        try:
            if attestation.hash_tree_root in self.attestation_pool:
                return True
            else:
                return not self.chain.attestation_exists(attestation.hash_tree_root)
        except AttestationNotFound:
            return True

    def _is_block_root_in_db(self, block_root: Hash32) -> bool:
        try:
            self.chain.get_block_by_root(block_root=block_root)
            return True
        except BlockNotFound:
            return False

    def _is_block_root_seen(self, block_root: Hash32) -> bool:
        return self._is_block_root_in_db(block_root=block_root)

    def _is_block_seen(self, block: BaseBeaconBlock) -> bool:
        return self._is_block_root_seen(block_root=block.signing_root)

    @to_tuple
    def get_ready_attestations(self) -> Iterable[Attestation]:
        state_machine = self.chain.get_state_machine()
        config = state_machine.config
        state = state_machine.state
        for attestation in self.attestation_pool.get_all():
            data = attestation.data
            attestation_slot = get_attestation_data_slot(state, data, config)
            try:
                validate_attestation_slot(
                    attestation_slot,
                    state.slot,
                    config.SLOTS_PER_EPOCH,
                    config.MIN_ATTESTATION_INCLUSION_DELAY,
                )
            except ValidationError:
                # TODO: Should clean up attestations with invalid slot because
                # they are no longer available for inclusion into block.
                continue
            else:
                yield attestation
