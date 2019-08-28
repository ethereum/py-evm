import abc
from pathlib import Path
from typing import Optional

from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.test_handler import TestHandler


class TestType(abc.ABC):
    name: str

    @classmethod
    def build_path(
        cls,
        tests_root_path: Path,
        test_handler: TestHandler,
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
