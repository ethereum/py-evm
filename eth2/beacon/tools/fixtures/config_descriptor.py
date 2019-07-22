from pathlib import Path
from typing import (
    Callable,
)

from eth2.beacon.tools.fixtures.config_types import ConfigType


class ConfigDescriptor:
    def __init__(self, config_type: ConfigType, config_path_provider: Callable[[ConfigType], Path]):
        self.config_type = config_type
        self._config_path_provider = config_path_provider

    @property
    def path(self):
        return self._config_path_provider(self.config_type)
