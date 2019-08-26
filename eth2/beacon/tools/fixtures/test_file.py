from dataclasses import dataclass
from typing import Sequence

from eth2.beacon.tools.fixtures.test_case import BaseTestCase
from eth2.configs import Eth2Config


@dataclass
class TestFile:
    file_name: str
    config: Eth2Config
    test_cases: Sequence[BaseTestCase]
