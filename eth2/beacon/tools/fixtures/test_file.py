from typing import (
    Sequence,
)
from dataclasses import (
    dataclass,
)

from eth2.configs import (
    Eth2Config,
)
from eth2.beacon.tools.fixtures.test_case import BaseStateTestCase


@dataclass
class TestFile:
    file_name: str
    config: Eth2Config
    test_cases: Sequence[BaseStateTestCase]
