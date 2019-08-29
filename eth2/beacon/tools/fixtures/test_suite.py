from dataclasses import dataclass
from typing import Tuple

from eth2.beacon.tools.fixtures.test_case import TestCase


@dataclass
class TestSuite:
    name: str
    test_cases: Tuple[TestCase, ...]
