import abc
from abc import abstractmethod
from typing import Any, Dict, Generic, Optional, TypeVar

from eth2.configs import Eth2Config

Input = TypeVar("Input")
Output = TypeVar("Output")


class TestHandler(abc.ABC, Generic[Input, Output]):
    name: str

    @classmethod
    @abstractmethod
    def parse_inputs(
        cls, test_case_data: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Input:
        ...

    @staticmethod
    @abstractmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> Output:
        ...

    @staticmethod
    def valid(data: Dict[str, Any]) -> bool:
        return True

    @classmethod
    @abstractmethod
    def run_with(cls, inputs: Input, config: Optional[Eth2Config]) -> Output:
        ...

    @staticmethod
    @abstractmethod
    def condition(output: Output, expected_output: Output) -> None:
        ...
