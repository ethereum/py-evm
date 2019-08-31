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
    @abstractmethod
    def load_ssz(
        cls, path: Path, ssz_class: Type[ssz.typing.TSerializable]
    ) -> ssz.typing.TSerializable:
        ...


class SSZType(FormatType):
    name = "ssz"

    @classmethod
    def load_yaml(cls, path: Path) -> Dict[str, Any]:
        raise NotImplementedError(
            f"the {cls} format type cannot load the request type `yaml`"
        )

    @classmethod
    def load_ssz(
        cls, path: Path, ssz_class: Type[ssz.typing.TSerializable]
    ) -> ssz.typing.TSerializable:
        with open(path, mode="rb") as f:
            data = f.read()
        return ssz_class.deserialize(data)


class YAMLType(FormatType):
    name = "yaml"

    @classmethod
    def load_yaml(cls, path: Path) -> Dict[str, Any]:
        return load_yaml_at(path)

    @classmethod
    def load_ssz(
        cls, path: Path, ssz_class: Type[ssz.typing.TSerializable]
    ) -> ssz.typing.TSerializable:
        raise NotImplementedError(
            f"the {cls} format type cannot load the request type `ssz`"
        )
