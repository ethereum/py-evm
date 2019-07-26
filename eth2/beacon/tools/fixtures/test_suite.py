from typing import (
    Any,
    Dict,
    Iterable,
    Sequence,
)

from eth2.configs import Eth2Config

from .test_case import TestCase
from .test_handler import TestHandler


def _parse_test_cases(config: Eth2Config,
                      test_handler: TestHandler,
                      test_cases: Sequence[Dict[str, Any]]) -> Iterable[TestCase]:
    for index, test_case in enumerate(test_cases):
        yield TestCase(
            index,
            test_case,
            test_handler(),
            config,
        )


class TestSuite:
    def __init__(self,
                 config: Eth2Config,
                 test_handler: TestHandler,
                 test_suite_data: Dict[str, Any]) -> None:
        self.test_cases = _parse_test_cases(
            config,
            test_handler,
            test_suite_data["test_cases"],
        )
