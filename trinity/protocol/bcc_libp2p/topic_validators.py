import logging
from typing import (
    Callable,
)

import ssz

from eth_utils import (
    ValidationError,
    encode_hex,
)

from eth.exceptions import BlockNotFound

from eth2.beacon.types.attestations import Attestation
from eth2.beacon.exceptions import SignatureError
from eth2.beacon.helpers import compute_epoch_of_slot
from eth2.beacon.chains.base import BaseBeaconChain
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.state_machines.forks.serenity.block_processing import process_block_header
from eth2.beacon.state_machines.forks.serenity.block_validation import validate_attestation

from libp2p.peer.id import ID
from libp2p.pubsub.pb import rpc_pb2

from trinity._utils.shellart import bold_red

logger = logging.getLogger('trinity.plugins.eth2.beacon.TopicValidator')


def get_beacon_block_validator(chain: BaseBeaconChain) -> Callable[..., bool]:
    def beacon_block_validator(msg_forwarder: ID, msg: rpc_pb2.Message) -> bool:
        try:
            block = ssz.decode(msg.data, BaseBeaconBlock)
        except (TypeError, ssz.DeserializationError) as error:
            logger.debug(
                bold_red("Failed to validate block=%s, error=%s"),
                encode_hex(block.signing_root),
                str(error),
            )
            return False

        state_machine = chain.get_state_machine()
        config = state_machine.config
        slots_per_epoch = config.SLOTS_PER_EPOCH
        state = chain.get_head_state()
        head_slot = state.slot
        current_epoch = compute_epoch_of_slot(head_slot, slots_per_epoch)
        block_epoch = compute_epoch_of_slot(block.slot, slots_per_epoch)
        if block_epoch > current_epoch:
            # Can not process block in future epoch because
            # proposer is not predictable.
            return False
        elif block_epoch < current_epoch:
            state_machine = chain.get_state_machine(block.slot)
            state = chain.get_state_by_slot(block.slot)

        state_transition = state_machine.state_transition
        # Fast forward to state in future slot in order to pass
        # block.slot validity check
        state = state_transition.apply_state_transition(
            state,
            future_slot=block.slot,
        )
        try:
            process_block_header(state, block, config, True)
        except (ValidationError, SignatureError) as error:
            logger.debug(
                bold_red("Failed to validate block=%s, error=%s"),
                encode_hex(block.signing_root),
                str(error),
            )
            return False
        else:
            return True
    return beacon_block_validator


def get_beacon_attestation_validator(chain: BaseBeaconChain) -> Callable[..., bool]:
    def beacon_attestation_validator(msg_forwarder: ID, msg: rpc_pb2.Message) -> bool:
        try:
            attestation = ssz.decode(msg.data, sedes=Attestation)
        except (TypeError, ssz.DeserializationError) as error:
            # Not correctly encoded
            logger.debug(
                bold_red("Failed to validate attestation=%s, error=%s"),
                attestation,
                str(error),
            )
            return False

        state_machine = chain.get_state_machine()
        config = state_machine.config
        # This appears to be an invalid property of the state machine.  Is this code dead?
        state = state_machine.state  # type: ignore

        # Check that beacon blocks attested to by the attestation are validated
        try:
            chain.get_block_by_root(attestation.data.beacon_block_root)
        except BlockNotFound:
            logger.debug(
                bold_red(
                    "Failed to validate attestation=%s, attested block=%s is not validated yet"
                ),
                attestation,
                encode_hex(attestation.data.beacon_block_root),
            )
            return False

        # Fast forward to state in future slot in order to pass
        # attestation.data.slot validity check
        future_state = state_machine.state_transition.apply_state_transition(
            state,
            future_slot=attestation.data.slot + config.MIN_ATTESTATION_INCLUSION_DELAY,
        )
        try:
            validate_attestation(
                future_state,
                attestation,
                config,
            )
        except ValidationError as error:
            logger.debug(
                bold_red("Failed to validate attestation=%s, error=%s"),
                attestation,
                str(error),
            )
            return False

        return True
    return beacon_attestation_validator
