from typing import Any, Dict, Sequence, Tuple

from eth_typing import Hash32
from eth_utils import decode_hex
from ssz.tools import from_formatted_dict

from eth2.beacon.genesis import (
    initialize_beacon_state_from_eth1,
    is_valid_genesis_state,
)
from eth2.beacon.tools.fixtures.conditions import validate_state
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.states import BeaconState
from eth2.configs import Eth2Config

from . import TestType


class ValidityHandler(TestHandler):
    name = "validity"

    def parse_inputs(self, test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["genesis"], BeaconState)

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> bool:
        return bool(test_case_data["is_valid"])

    def run_with(self, genesis_state: BeaconState, config: Eth2Config) -> bool:
        return is_valid_genesis_state(genesis_state, config)

    def condition(self, output: bool, expected_output: bool) -> None:
        assert output == expected_output


class InitializationHandler(TestHandler):
    name = "initialization"

    def parse_inputs(
        self, test_case_data: Dict[str, Any]
    ) -> Tuple[Hash32, int, Tuple[Deposit]]:
        return (
            decode_hex(test_case_data["eth1_block_hash"]),
            test_case_data["eth1_timestamp"],
            tuple(
                from_formatted_dict(deposit_data, Deposit)
                for deposit_data in test_case_data["deposits"]
            ),
        )

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["state"], BeaconState)

    def run_with(
        self, inputs: Tuple[Hash32, int, Tuple[Deposit]], config: Eth2Config
    ) -> BeaconState:
        eth1_block_hash, eth1_timestamp, deposits = inputs

        return initialize_beacon_state_from_eth1(
            eth1_block_hash=eth1_block_hash,
            eth1_timestamp=eth1_timestamp,
            deposits=deposits,
            config=config,
        )

    def condition(self, output: BeaconState, expected_output: BeaconState) -> None:
        validate_state(output, expected_output)


class GenesisTestType(TestType):
    name = "genesis"

    handlers = (ValidityHandler, InitializationHandler)
