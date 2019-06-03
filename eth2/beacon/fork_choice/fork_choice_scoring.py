from typing import Callable

from eth2.beacon.types.blocks import BaseBeaconBlock

ForkChoiceScoring = Callable[[BaseBeaconBlock], int]
