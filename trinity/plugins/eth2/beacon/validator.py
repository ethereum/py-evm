import logging
from typing import (
    Dict,
    cast,
)

from cancel_token import (
    CancelToken,
)

from eth_typing import (
    Hash32,
)

from eth2.beacon.chains.base import BeaconChain
from eth2.beacon.helpers import (
    slot_to_epoch,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.state_machines.base import BaseBeaconStateMachine  # noqa: F401
from eth2.beacon.tools.builder.proposer import (
    _get_proposer_index,
    create_block_on_state,
)
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Epoch,
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
from eth2.configs import (
    Eth2GenesisConfig,
)


class Validator(BaseService):
    chain: BeaconChain
    peer_pool: BCCPeerPool
    validator_privkeys: Dict[ValidatorIndex, int]
    event_bus: TrinityEventBusEndpoint
    slots_per_epoch: int
    latest_proposed_epoch: Epoch

    logger = logging.getLogger('trinity.plugins.eth2.beacon.Validator')

    def __init__(
            self,
            chain: BeaconChain,
            peer_pool: BCCPeerPool,
            validator_privkeys: Dict[ValidatorIndex, int],
            genesis_config: Eth2GenesisConfig,
            event_bus: TrinityEventBusEndpoint,
            token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.peer_pool = peer_pool
        self.validator_privkeys = validator_privkeys
        self.event_bus = event_bus
        # TODO: `latest_proposed_epoch` should be written into/read from validator's own db
        self.latest_proposed_epoch = genesis_config.GENESIS_EPOCH
        self.slots_per_epoch = genesis_config.SECONDS_PER_SLOT

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
            await self.propose_or_skip_block(event.slot, event.is_second_tick)

    async def propose_or_skip_block(self, slot: Slot, is_second_tick: bool) -> None:
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
        # Since it's expected to tick twice in one slot, `latest_proposed_epoch` is used to prevent
        # proposing twice in the same slot.
        has_proposed = slot_to_epoch(slot, self.slots_per_epoch) <= self.latest_proposed_epoch
        if not has_proposed and proposer_index in self.validator_privkeys:
            self.propose_block(
                proposer_index=proposer_index,
                slot=slot,
                state=state,
                state_machine=state_machine,
                head_block=head,
            )
            self.latest_proposed_epoch = slot_to_epoch(slot, self.slots_per_epoch)
        # skip the block if it's second half of the slot and we are not proposing
        elif is_second_tick and proposer_index not in self.validator_privkeys:
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
            bold_green(f"proposing block, block={block}")
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
