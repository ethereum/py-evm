from typing import Any, Dict, Tuple, Type, cast

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
from eth2.beacon.typing import Timestamp
from eth2.configs import Eth2Config

from . import TestType


class ValidityHandler(TestHandler[BeaconState, bool]):
    name = "validity"

    @classmethod
    def parse_inputs(_cls, test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["genesis"], BeaconState)

    @staticmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> bool:
        return bool(test_case_data["is_valid"])

    @classmethod
    def run_with(_cls, genesis_state: BeaconState, config: Eth2Config) -> bool:
        return is_valid_genesis_state(genesis_state, config)

    @staticmethod
    def condition(output: bool, expected_output: bool) -> None:
        assert output == expected_output


class InitializationHandler(
    TestHandler[Tuple[Hash32, Timestamp, Tuple[Deposit, ...]], BeaconState]
):
    name = "initialization"

    @classmethod
    def parse_inputs(
        _cls, test_case_data: Dict[str, Any]
    ) -> Tuple[Hash32, Timestamp, Tuple[Deposit, ...]]:
        return (
            cast(Hash32, decode_hex(test_case_data["eth1_block_hash"])),
            Timestamp(test_case_data["eth1_timestamp"]),
            tuple(
                cast(Deposit, from_formatted_dict(deposit_data, Deposit))
                for deposit_data in test_case_data["deposits"]
            ),
        )

    @staticmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["state"], BeaconState)

    @classmethod
    def run_with(
        _cls, inputs: Tuple[Hash32, Timestamp, Tuple[Deposit, ...]], config: Eth2Config
    ) -> BeaconState:
        eth1_block_hash, eth1_timestamp, deposits = inputs

        return initialize_beacon_state_from_eth1(
            eth1_block_hash=eth1_block_hash,
            eth1_timestamp=eth1_timestamp,
            deposits=deposits,
            config=config,
        )

    @staticmethod
    def condition(output: BeaconState, expected_output: BeaconState) -> None:
        validate_state(output, expected_output)


GenesisHandlerType = Tuple[Type[ValidityHandler], Type[InitializationHandler]]


class GenesisTestType(TestType[GenesisHandlerType]):
    name = "genesis"

    handlers = (ValidityHandler, InitializationHandler)
