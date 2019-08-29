import abc


class FormatType(abc.ABC):
    name: str


class SSZType(FormatType):
    name = "ssz"


class YAMLType(FormatType):
    name = "yaml"
