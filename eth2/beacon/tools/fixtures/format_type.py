import abc
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, Type

import ssz

from eth2.beacon.tools.fixtures.loading import load_yaml_at


class FormatType(abc.ABC):
    name: str

    @classmethod
    @abstractmethod
    def load_yaml(cls, path: Path) -> Any:
        ...

    @classmethod
    def load_ssz(
        cls, path: Path, ssz_class: Type[ssz.typing.TSerializable]
    ) -> ssz.typing.TSerializable:
        data = cls.load_bytes(path)
        return ssz_class.deserialize(data)

    @classmethod
    @abstractmethod
    def load_bytes(cls, path: Path) -> bytes:
        ...


class SSZType(FormatType):
    name = "ssz"

    @classmethod
    def load_yaml(cls, path: Path) -> Dict[str, Any]:
        raise NotImplementedError(
            f"the {cls} format type cannot load the request type `yaml`"
        )

    @classmethod
    def load_bytes(cls, path: Path) -> bytes:
        with open(path, mode="rb") as f:
            return f.read()


class YAMLType(FormatType):
    name = "yaml"

    @classmethod
    def load_yaml(cls, path: Path) -> Dict[str, Any]:
        return load_yaml_at(path)

    @classmethod
    def load_bytes(cls, path: Path) -> bytes:
        raise NotImplementedError(
            f"the {cls} format type cannot load the request type `ssz`"
        )
