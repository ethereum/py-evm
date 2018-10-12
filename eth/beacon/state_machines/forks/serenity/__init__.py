
from typing import Type  # noqa: F401

from eth.beacon.types.active_states import ActiveState  # noqa: F401
from eth.beacon.types.attestation_records import AttestationRecord  # noqa: F401
from eth.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
from eth.beacon.types.crystallized_states import CrystallizedState  # noqa: F401

from eth.beacon.state_machines.base import BeaconStateMachine

from .active_states import SerenityActiveState
from .attestation_records import SerenityAttestationRecord
from .blocks import SerenityBeaconBlock
from .crystallized_states import SerenityCrystallizedState
from .configs import SERENITY_CONFIG


class SerenityStateMachine(BeaconStateMachine):
    # fork name
    fork = 'serenity'  # type: str

    # classes
    block_class = SerenityBeaconBlock  # type: Type[BaseBeaconBlock]
    crystallized_state_class = SerenityCrystallizedState  # type: Type[CrystallizedState]
    active_state_class = SerenityActiveState  # type: Type[ActiveState]
    attestation_record_class = SerenityAttestationRecord  # type: Type[AttestationRecord]
    config = SERENITY_CONFIG
