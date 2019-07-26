from typing import (
    Any,
    Dict,
    Sequence,
    Tuple,
)

from eth_utils import (
    decode_hex,
)

from eth2.beacon.committee_helpers import (
    compute_shuffled_index,
)
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.configs import Eth2Config

from . import TestType


class CoreHandler(TestHandler):
    name = "core"

    def parse_inputs(self, test_case_data: Dict[str, Any]) -> Tuple[int, bytes]:
        return (
            test_case_data["count"],
            decode_hex(test_case_data["seed"]),
        )

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> Tuple[int]:
        return tuple(test_case_data["shuffled"])

    def run_with(self,
                 inputs: Any,
                 config: Eth2Config,
                 *_auxillary: Sequence[Any]) -> Tuple[int]:
        count, seed = inputs
        return tuple(
            compute_shuffled_index(
                index,
                count,
                seed,
                config.SHUFFLE_ROUND_COUNT
            )
            for index in range(count)
        )

    def condition(self, output: Any, expected_output: Any) -> None:
        assert output == expected_output


class ShufflingTestType(TestType):
    name = "shuffling"

    handlers = (
        CoreHandler,
    )
