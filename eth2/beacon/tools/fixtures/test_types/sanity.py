from typing import (
    Any,
    Dict,
)

from eth2.beacon.tools.fixtures.test_type import TestType

from eth2.configs import Eth2Config


class Sanity(TestType):
    def __init__(self, config: Eth2Config, data: Dict[str, Any]) -> None:
        pass

    @staticmethod
    def name() -> str:
        return "sanity"
