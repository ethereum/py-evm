"""
A blockchain has a way to pick a canonical chain from the block tree called a fork choice.
A fork choice works by using a scoring rule to attach a scalar quantity to a particular block
given our local view of the network.

The fork choice provides a "canonical" path through the block tree by recursively selecting the
highest scoring child of a given block until we terminate at the tip of the chain.

This module provides a variety of fork choice rules. Clients can introduce new rules here to
experiment with alternative fork choice methods.
"""

from typing import Callable

from eth2.beacon.types.blocks import BaseBeaconBlock

ScoringFn = Callable[[BaseBeaconBlock], int]
