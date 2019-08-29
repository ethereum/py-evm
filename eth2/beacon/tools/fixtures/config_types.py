import abc
from typing import Optional


class ConfigType(abc.ABC):
    name: str
    path: Optional[str] = "config.yaml"

    @classmethod
    def has_config(cls) -> bool:
        """
        Return ``True`` if this ``ConfigType`` has configuration that should be loaded.
        """
        return cls.path is not None


class Mainnet(ConfigType):
    name = "mainnet"


class Minimal(ConfigType):
    name = "minimal"


class General(ConfigType):
    """
    ``General`` covers the set of tests that function independent of a particular config.
    """

    name = "general"
    path = None
