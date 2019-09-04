from typing import Any, Dict, Optional, Tuple, Type

from eth_utils import decode_hex

from eth2.beacon.committee_helpers import compute_shuffled_index
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.configs import Eth2Config

from . import TestType


class CoreHandler(TestHandler[Tuple[int, bytes], Tuple[int, ...]]):
    name = "core"

    @classmethod
    def parse_inputs(
        _cls, test_case_parts: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Tuple[int, bytes]:
        test_case_data = test_case_parts["mapping"].load()
        return (test_case_data["count"], decode_hex(test_case_data["seed"]))

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, Any]) -> Tuple[int, ...]:
        test_case_data = test_case_parts["mapping"].load()
        return tuple(int(data) for data in test_case_data["mapping"])

    @classmethod
    def run_with(_cls, inputs: Any, config: Optional[Eth2Config]) -> Tuple[int, ...]:
        count, seed = inputs
        return tuple(
            compute_shuffled_index(index, count, seed, config.SHUFFLE_ROUND_COUNT)
            for index in range(count)
        )

    @staticmethod
    def condition(output: Any, expected_output: Any) -> None:
        assert output == expected_output


ShufflingHandlerType = Tuple[Type[CoreHandler]]


class ShufflingTestType(TestType[ShufflingHandlerType]):
    name = "shuffling"

    handlers = (CoreHandler,)
