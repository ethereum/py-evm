import abc


class ConfigType(abc.ABC):
    name: str
    path: str


class Mainnet(ConfigType):
    # name is the human-readable name for this configuration.
    name = "mainnet"
    # path is the file system path to the config as YAML, relative to the project root.
    path = "tests/eth2/fixtures/mainnet.yaml"


class Full(Mainnet):
    name = "full"


class Minimal(ConfigType):
    # name is the human-readable name for this configuration.
    name = "minimal"
    # path is the file system path to the config as YAML, relative to the project root.
    path = "tests/eth2/fixtures/minimal.yaml"
