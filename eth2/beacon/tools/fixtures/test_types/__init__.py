from pathlib import Path

from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.test_handler import TestHandler


class TestType:
    # TODO(ralexstokes) simplify to just ``file_name``?
    @classmethod
    def build_path(cls,
                   tests_root_path: Path,
                   test_handler: TestHandler,
                   config_type: ConfigType) -> Path:
        if len(cls.handlers) == 1:
            file_name = f"{cls.name}_{config_type.name}.yaml"
        else:
            file_name = f"{cls.name}_{test_handler.name}_{config_type.name}.yaml"
        return tests_root_path / Path(cls.name) / Path(test_handler.name) / Path(file_name)
