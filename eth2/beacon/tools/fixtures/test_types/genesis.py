from typing import Any, Dict, Optional, Tuple, Type, cast

from eth_typing import Hash32
from ssz.sedes import bytes32

from eth2.beacon.genesis import (
    initialize_beacon_state_from_eth1,
    is_valid_genesis_state,
)
from eth2.beacon.tools.fixtures.conditions import validate_state
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.tools.fixtures.test_part import TestPart
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Timestamp
from eth2.configs import Eth2Config

from . import TestType


class ValidityHandler(TestHandler[BeaconState, bool]):
    name = "validity"

    @classmethod
    def parse_inputs(
        _cls, test_case_parts: Dict[str, TestPart], metadata: Dict[str, Any]
    ) -> BeaconState:
        return test_case_parts["genesis"].load(BeaconState)

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, TestPart]) -> bool:
        return bool(test_case_parts["is_valid"].load())

    @classmethod
    def run_with(
        _cls, genesis_state: BeaconState, config: Optional[Eth2Config]
    ) -> bool:
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
        _cls, test_case_parts: Dict[str, TestPart], metadata: Dict[str, Any]
    ) -> Tuple[Hash32, Timestamp, Tuple[Deposit, ...]]:
        deposits_count = metadata["deposits_count"]
        return (
            cast(Hash32, test_case_parts["eth1_block_hash"].load(bytes32)),
            Timestamp(test_case_parts["eth1_timestamp"].load()),
            tuple(
                cast(Deposit, test_case_parts[f"deposits_{i}"].load(Deposit))
                for i in range(deposits_count)
            ),
        )

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, TestPart]) -> BeaconState:
        return test_case_parts["state"].load(BeaconState)

    @classmethod
    def run_with(
        _cls,
        inputs: Tuple[Hash32, Timestamp, Tuple[Deposit, ...]],
        config: Optional[Eth2Config],
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
