from itertools import groupby
import logging
from operator import itemgetter
from typing import (
    Dict,
    Iterable,
    Tuple,
    cast,
)

from cancel_token import (
    CancelToken,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    to_tuple,
)

from eth2.beacon.chains.base import BeaconChain
from eth2.beacon.helpers import (
    slot_to_epoch,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.state_machines.base import BaseBeaconStateMachine  # noqa: F401
from eth2.beacon.tools.builder.committee_assignment import CommitteeAssignment
from eth2.beacon.tools.builder.proposer import (
    _get_proposer_index,
    create_block_on_state,
)
from eth2.beacon.tools.builder.validator import (
    create_signed_attestation_at_slot,
    get_committee_assignment,
)
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Epoch,
    Shard,
    Slot,
    ValidatorIndex,
)

from p2p.service import BaseService

from trinity._utils.shellart import (
    bold_green,
    bold_red,
)
from trinity.endpoint import TrinityEventBusEndpoint
from trinity.protocol.bcc.peer import (
    BCCPeer,
    BCCPeerPool,
)
from trinity.plugins.eth2.beacon.slot_ticker import (
    SlotTickEvent,
)


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

    async def _run(self) -> None:
        await self.event_bus.wait_until_serving()
        self.logger.debug(bold_green("validator running!!!"))
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
                    # FIXME: in simple testnet, `registry_change` is not likely to change
                    # so hardcode it as `False`.
                    registry_change=False,
                )
            )
        return self.this_epoch_assignment[validator_index][1]

    async def handle_first_tick(self, slot: Slot) -> None:
        head = self.chain.get_canonical_head()
        state_machine = self.chain.get_state_machine()
        state = state_machine.state
        self.logger.debug(
            bold_green(f"head: slot={head.slot}, state root={head.state_root.hex()}")
        )
        proposer_index = _get_proposer_index(
            state,
            slot,
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

        await self.attest(slot)

    async def handle_second_tick(self, slot: Slot) -> None:
        head = self.chain.get_canonical_head()
        state_machine = self.chain.get_state_machine()
        state = state_machine.state
        self.logger.debug(
            bold_green(f"head: slot={head.slot}, state root={head.state_root.hex()}")
        )
        if state.slot < slot:
            self.skip_block(
                slot=slot,
                state=state,
                state_machine=state_machine,
            )

    def propose_block(self,
                      proposer_index: ValidatorIndex,
                      slot: Slot,
                      state: BeaconState,
                      state_machine: BaseBeaconStateMachine,
                      head_block: BaseBeaconBlock) -> BaseBeaconBlock:
        block = self._make_proposing_block(
            proposer_index=proposer_index,
            slot=slot,
            state=state,
            state_machine=state_machine,
            parent_block=head_block,
        )
        self.logger.debug(
            bold_green(f"validator index={proposer_index} proposing block, block={block}")
        )
        for peer in self.peer_pool.connected_nodes.values():
            peer = cast(BCCPeer, peer)
            self.logger.debug(
                bold_red(f"sending block to peer={peer}")
            )
            peer.sub_proto.send_new_block(block)
        self.chain.import_block(block)
        return block

    def _make_proposing_block(self,
                              proposer_index: ValidatorIndex,
                              slot: Slot,
                              state: BeaconState,
                              state_machine: BaseBeaconStateMachine,
                              parent_block: BaseBeaconBlock) -> BaseBeaconBlock:
        return create_block_on_state(
            state=state,
            config=state_machine.config,
            state_machine=state_machine,
            block_class=SerenityBeaconBlock,
            parent_block=parent_block,
            slot=slot,
            validator_index=proposer_index,
            privkey=self.validator_privkeys[proposer_index],
            attestations=(),
            check_proposer_index=False,
        )

    def skip_block(self,
                   slot: Slot,
                   state: BeaconState,
                   state_machine: BaseBeaconStateMachine) -> Hash32:
        post_state = state_machine.state_transition.apply_state_transition_without_block(
            state,
            # TODO: Change back to `slot` instead of `slot + 1`.
            # Currently `apply_state_transition_without_block` only returns the post state
            # of `slot - 1`, so we increment it by one to get the post state of `slot`.
            cast(Slot, slot + 1),
        )
        self.logger.debug(
            bold_green(f"skipping block, post state={post_state.root}")
        )
        # FIXME: We might not need to persist state for skip slots since `create_block_on_state`
        # will run the state transition which also includes the state transition for skipped slots.
        self.chain.chaindb.persist_state(post_state)
        return post_state.root

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
                bold_green(
                    f"validator index={attesting_validators_indices} attest to block, "
                    f"block={head}, attestation={attestation}"
                )
            )
            for validator_index in attesting_validators_indices:
                self.latest_attested_epoch[validator_index] = epoch
            attestations = attestations + (attestation,)

        for peer in self.peer_pool.connected_nodes.values():
            peer = cast(BCCPeer, peer)
            self.logger.debug(
                bold_red(f"sending attestations to peer={peer}")
            )
            peer.sub_proto.send_attestation_records(attestations)
        return attestations
