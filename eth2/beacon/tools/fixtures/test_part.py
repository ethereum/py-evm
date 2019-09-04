from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Type, cast

import ssz

from eth2.beacon.tools.fixtures.format_type import FormatType, SSZType, YAMLType


@dataclass
class TestPart:
    parts: Dict[Type[FormatType], Path]

    def load_yaml(self) -> Any:
        if YAMLType in self.parts:
            return YAMLType.load_yaml(self.parts[YAMLType])
        return None

    def load_bytes(self) -> bytes:
        if SSZType in self.parts:
            return SSZType.load_bytes(self.parts[SSZType])
        return bytes()

    def load(self, *args: Any) -> Any:
        # NOTE: implicit preference for formats here
        # may want to allow the caller more control in the future

        # NOTE: probably want to deprecate this in favor of the explicit loading methods...

        if SSZType in self.parts:
            return SSZType.load_ssz(
                self.parts[SSZType], cast(Type[ssz.typing.TSerializable], args[0])
            )
        elif YAMLType in self.parts:
            return YAMLType.load_yaml(self.parts[YAMLType])
        else:
            raise AssertionError(
                "missing a recognized format in ``TestPart``; check fixtures data"
            )
