from itertools import (
    groupby,
)
import logging
from operator import (
    itemgetter,
)
from typing import (
    Callable,
    Dict,
    Iterable,
    Sequence,
    Tuple,
    cast,
)

from cancel_token import (
    CancelToken,
)
from eth_utils import (
    encode_hex,
    to_tuple,
)

from eth2.beacon.chains.base import (
    BeaconChain,
)
from eth2.beacon.helpers import (
    slot_to_epoch,
)
from eth2.beacon.state_machines.base import (
    BaseBeaconStateMachine,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.tools.builder.committee_assignment import (
    CommitteeAssignment,
)
from eth2.beacon.tools.builder.proposer import (
    _get_proposer_index,
    create_block_on_state,
)
from eth2.beacon.tools.builder.committee_assignment import (
    get_committee_assignment,
)
from eth2.beacon.tools.builder.validator import (
    create_signed_attestation_at_slot,
)
from eth2.beacon.types.attestations import (
    Attestation,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth2.beacon.types.states import (
    BeaconState,
)
from eth2.beacon.typing import (
    Epoch,
    Shard,
    Slot,
    ValidatorIndex,
)
from p2p.service import (
    BaseService,
)
from trinity._utils.shellart import (
    bold_green,
    bold_red,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.plugins.eth2.beacon.slot_ticker import (
    SlotTickEvent,
)
from trinity.protocol.bcc.peer import (
    BCCPeer,
    BCCPeerPool,
)


GetReadyAttestationsFn = Callable[[], Sequence[Attestation]]


class Validator(BaseService):
    chain: BeaconChain
    peer_pool: BCCPeerPool
    validator_privkeys: Dict[ValidatorIndex, int]
    event_bus: TrinityEventBusEndpoint
    slots_per_epoch: int
    latest_proposed_epoch: Dict[ValidatorIndex, Epoch]
    latest_attested_epoch: Dict[ValidatorIndex, Epoch]
    this_epoch_assignment: Dict[ValidatorIndex, Tuple[Epoch, CommitteeAssignment]]

    logger = logging.getLogger('trinity.plugins.eth2.beacon.Validator')

    def __init__(
            self,
            chain: BeaconChain,
            peer_pool: BCCPeerPool,
            validator_privkeys: Dict[ValidatorIndex, int],
            event_bus: TrinityEventBusEndpoint,
            get_ready_attestations_fn: GetReadyAttestationsFn,
            token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.peer_pool = peer_pool
        self.validator_privkeys = validator_privkeys
        self.event_bus = event_bus
        config = self.chain.get_state_machine().config
        self.slots_per_epoch = config.SLOTS_PER_EPOCH
        # TODO: `latest_proposed_epoch` and `latest_attested_epoch` should be written
        # into/read from validator's own db.
        self.latest_proposed_epoch = {}
        self.latest_attested_epoch = {}
        self.this_epoch_assignment = {}
        for validator_index in validator_privkeys:
            self.latest_proposed_epoch[validator_index] = Epoch(-1)
            self.latest_attested_epoch[validator_index] = Epoch(-1)
            self.this_epoch_assignment[validator_index] = (
                Epoch(-1),
                CommitteeAssignment((), Shard(-1), Slot(-1), False),
            )
        self.get_ready_attestations: GetReadyAttestationsFn = get_ready_attestations_fn

    async def _run(self) -> None:
        self.logger.info(
            bold_green("Validator service up  Handle indices=%s"),
            tuple(self.validator_privkeys.keys())
        )
        self.run_daemon_task(self.handle_slot_tick())
        await self.cancellation()

    async def handle_slot_tick(self) -> None:
        """
        The callback for `SlotTicker` and it's expected to be called twice for one slot.
        """
        async for event in self.event_bus.stream(SlotTickEvent):
            if not event.is_second_tick:
                await self.handle_first_tick(event.slot)
            else:
                await self.handle_second_tick(event.slot)

    def _get_this_epoch_assignment(self,
                                   validator_index: ValidatorIndex,
                                   this_epoch: Epoch) -> CommitteeAssignment:
        # update `this_epoch_assignment` if it's outdated
        if this_epoch > self.this_epoch_assignment[validator_index][0]:
            state_machine = self.chain.get_state_machine()
            state = state_machine.state
            self.this_epoch_assignment[validator_index] = (
                this_epoch,
                get_committee_assignment(
                    state,
                    state_machine.config,
                    this_epoch,
                    validator_index,
                )
            )
        return self.this_epoch_assignment[validator_index][1]

    async def handle_first_tick(self, slot: Slot) -> None:
        head = self.chain.get_canonical_head()
        state_machine = self.chain.get_state_machine()
        state = state_machine.state
        self.logger.debug(
            # Align with debug log below
            bold_green("Head       epoch=%s slot=%s state_root=%s"),
            state.current_epoch(self.slots_per_epoch),
            head.slot,
            encode_hex(head.state_root),
        )
        self.logger.debug(
            bold_green("Justified  epoch=%s root=%s  (current)"),
            state.current_justified_epoch,
            encode_hex(state.current_justified_root),
        )
        self.logger.debug(
            bold_green("Justified  epoch=%s root=%s  (previous)"),
            state.previous_justified_epoch,
            encode_hex(state.previous_justified_root),
        )
        self.logger.debug(
            bold_green("Finalized  epoch=%s root=%s"),
            state.finalized_epoch,
            encode_hex(state.finalized_root),
        )
        self.logger.debug(
            bold_green("current_epoch_attestations  %s"),
            state.current_epoch_attestations,
        )
        self.logger.debug(
            bold_green("previous_epoch_attestations %s"),
            state.previous_epoch_attestations,
        )
        proposer_index = _get_proposer_index(
            state.copy(
                slot=slot,
            ),
            state_machine.config,
        )
        # `latest_proposed_epoch` is used to prevent validator from erraneously proposing twice
        # in the same epoch due to service crashing.
        epoch = slot_to_epoch(slot, self.slots_per_epoch)
        if proposer_index in self.validator_privkeys:
            has_proposed = epoch <= self.latest_proposed_epoch[proposer_index]
            if not has_proposed:
                self.propose_block(
                    proposer_index=proposer_index,
                    slot=slot,
                    state=state,
                    state_machine=state_machine,
                    head_block=head,
                )
                self.latest_proposed_epoch[proposer_index] = epoch

    async def handle_second_tick(self, slot: Slot) -> None:
        state_machine = self.chain.get_state_machine()
        state = state_machine.state
        if state.slot < slot:
            self.skip_block(
                slot=slot,
                state=state,
                state_machine=state_machine,
            )

        await self.attest(slot)

    def propose_block(self,
                      proposer_index: ValidatorIndex,
                      slot: Slot,
                      state: BeaconState,
                      state_machine: BaseBeaconStateMachine,
                      head_block: BaseBeaconBlock) -> BaseBeaconBlock:
        ready_attestations = self.get_ready_attestations()
        block = self._make_proposing_block(
            proposer_index=proposer_index,
            slot=slot,
            state=state,
            state_machine=state_machine,
            parent_block=head_block,
            attestations=ready_attestations,
        )
        self.logger.info(
            bold_green("Validator=%s proposing block=%s with attestations=%s"),
            proposer_index,
            block,
            block.body.attestations,
        )
        for peer in self.peer_pool.connected_nodes.values():
            peer = cast(BCCPeer, peer)
            self.logger.debug(bold_red("Sending block=%s to peer=%s"), block, peer)
            peer.sub_proto.send_new_block(block)
        self.chain.import_block(block)
        return block

    def _make_proposing_block(self,
                              proposer_index: ValidatorIndex,
                              slot: Slot,
                              state: BeaconState,
                              state_machine: BaseBeaconStateMachine,
                              parent_block: BaseBeaconBlock,
                              attestations: Sequence[Attestation]) -> BaseBeaconBlock:
        return create_block_on_state(
            state=state,
            config=state_machine.config,
            state_machine=state_machine,
            block_class=SerenityBeaconBlock,
            parent_block=parent_block,
            slot=slot,
            validator_index=proposer_index,
            privkey=self.validator_privkeys[proposer_index],
            attestations=attestations,
            check_proposer_index=False,
        )

    def skip_block(self,
                   slot: Slot,
                   state: BeaconState,
                   state_machine: BaseBeaconStateMachine) -> BeaconState:
        post_state = state_machine.state_transition.apply_state_transition(
            state,
            future_slot=slot,
        )
        self.logger.debug(
            bold_green("Skip block at slot=%s  post_state=%s"),
            slot,
            post_state,
        )
        # FIXME: We might not need to persist state for skip slots since `create_block_on_state`
        # will run the state transition which also includes the state transition for skipped slots.
        self.chain.chaindb.persist_state(post_state)
        return post_state

    def _is_attesting(self,
                      validator_index: ValidatorIndex,
                      assignment: CommitteeAssignment,
                      slot: Slot,
                      epoch: Epoch) -> bool:
        has_attested = epoch <= self.latest_attested_epoch[validator_index]
        return not has_attested and slot == assignment.slot

    @to_tuple
    def _get_attesting_validator_and_shard(self,
                                           assignments: Dict[ValidatorIndex, CommitteeAssignment],
                                           slot: Slot,
                                           epoch: Epoch) -> Iterable[Tuple[ValidatorIndex, Shard]]:
        for validator_index, assignment in assignments.items():
            if self._is_attesting(validator_index, assignment, slot, epoch):
                yield (validator_index, assignment.shard)

    async def attest(self, slot: Slot) -> Tuple[Attestation, ...]:
        attestations: Tuple[Attestation, ...] = ()
        head = self.chain.get_canonical_head()
        state_machine = self.chain.get_state_machine()
        state = state_machine.state
        epoch = slot_to_epoch(slot, self.slots_per_epoch)

        validator_assignments = {
            validator_index: self._get_this_epoch_assignment(
                validator_index,
                epoch,
            )
            for validator_index in self.validator_privkeys
        }
        attesting_validators = self._get_attesting_validator_and_shard(
            validator_assignments,
            slot,
            epoch,
        )
        if len(attesting_validators) == 0:
            return ()

        # Sort the attesting validators by shard
        sorted_attesting_validators = sorted(
            attesting_validators,
            key=itemgetter(1),
        )
        # Group the attesting validators by shard
        attesting_validators_groups = groupby(
            sorted_attesting_validators,
            key=itemgetter(1),
        )
        for shard, group in attesting_validators_groups:
            # Get the validator_index -> privkey map of the attesting validators
            attesting_validator_privkeys = {
                attesting_data[0]: self.validator_privkeys[attesting_data[0]]
                for attesting_data in group
            }
            attesting_validators_indices = tuple(attesting_validator_privkeys.keys())
            # Get one of the attesting validator's assignment in order to get the committee info
            assignment = self._get_this_epoch_assignment(
                attesting_validators_indices[0],
                epoch,
            )
            attestation = create_signed_attestation_at_slot(
                state,
                state_machine.config,
                state_machine,
                slot,
                head.signing_root,
                attesting_validator_privkeys,
                assignment.committee,
                shard,
            )
            self.logger.debug(
                bold_green("Validators=%s attest to block=%s  attestation=%s"),
                attesting_validators_indices,
                head,
                attestation,
            )
            for validator_index in attesting_validators_indices:
                self.latest_attested_epoch[validator_index] = epoch
            attestations = attestations + (attestation,)

        for peer in self.peer_pool.connected_nodes.values():
            peer = cast(BCCPeer, peer)
            self.logger.debug(bold_red("Sending attestations=%s to peer=%s"), attestations, peer)
            peer.sub_proto.send_attestation_records(attestations)
        return attestations
