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
from eth2.beacon.chains.base import BaseBeaconChain
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_attestation,
    validate_proposer_signature,
)
from eth2.beacon.typing import Slot
from eth2.configs import CommitteeConfig

from libp2p.peer.id import ID
from libp2p.pubsub.pb import rpc_pb2

from trinity._utils.shellart import bold_red

logger = logging.getLogger('trinity.components.eth2.beacon.TopicValidator')


def get_beacon_block_validator(chain: BaseBeaconChain) -> Callable[..., bool]:
    def beacon_block_validator(msg_forwarder: ID, msg: rpc_pb2.Message) -> bool:
        try:
            block = ssz.decode(msg.data, BeaconBlock)
        except (TypeError, ssz.DeserializationError) as error:
            logger.debug(
                bold_red("Failed to validate block=%s, error=%s"),
                encode_hex(block.signing_root),
                str(error),
            )
            return False

        state_machine = chain.get_state_machine(block.slot - 1)
        state_transition = state_machine.state_transition
        state = chain.get_head_state()
        # Fast forward to state in future slot in order to pass
        # block.slot validity check
        state = state_transition.apply_state_transition(
            state,
            future_slot=block.slot,
        )
        try:
            validate_proposer_signature(state, block, CommitteeConfig(state_machine.config))
        except ValidationError as error:
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
        state = chain.get_head_state()

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
            future_slot=Slot(attestation.data.slot + config.MIN_ATTESTATION_INCLUSION_DELAY),
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
