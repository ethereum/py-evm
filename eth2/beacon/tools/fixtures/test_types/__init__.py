import abc
from pathlib import Path
from typing import Generic, Optional, Sized, TypeVar

from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.test_handler import Input, Output, TestHandler

HandlerType = TypeVar("HandlerType", bound=Sized)


class TestType(abc.ABC, Generic[HandlerType]):
    name: str
    handlers: HandlerType

    @classmethod
    def build_path(
        cls,
        tests_root_path: Path,
        test_handler: TestHandler[Input, Output],
        config_type: Optional[ConfigType],
    ) -> Path:
        if len(cls.handlers) == 1:
            file_name = f"{cls.name}"
        else:
            file_name = f"{cls.name}_{test_handler.name}"

        if config_type:
            file_name += f"_{config_type.name}"

        file_name += ".yaml"

        return (
            tests_root_path / Path(cls.name) / Path(test_handler.name) / Path(file_name)
        )
