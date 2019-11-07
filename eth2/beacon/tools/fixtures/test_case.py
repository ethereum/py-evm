from enum import Enum
from typing import Any, Dict, Optional

from eth2._utils.bls import bls
from eth2._utils.bls.backends import MilagroBackend
from eth2.beacon.tools.fixtures.test_part import TestPart
from eth2.configs import Eth2Config

from .test_handler import Input, Output, TestHandler


class BLSSetting(Enum):
    OPTIONAL = 0
    ENABLED = 1
    DISABLED = 2


def _select_bls_backend(bls_setting: BLSSetting) -> None:
    if bls_setting == BLSSetting.DISABLED:
        bls.use_noop_backend()
    elif bls_setting == BLSSetting.ENABLED:
        bls.use(MilagroBackend)
    elif bls_setting == BLSSetting.OPTIONAL:
        # do not verify BLS to save time
        bls.use_noop_backend()


# META_KEY is the prefix of the filename of the YAML file storing metadata about a test case.
# e.g. in the context of a test case file tree, there is a file `meta.yaml`.
META_KEY = "meta"

BLS_SETTING_KEY = "bls_setting"


class TestCase:
    name: str
    handler: TestHandler[Any, Any]
    test_case_parts: Dict[str, TestPart]
    config: Optional[Eth2Config]

    def __init__(
        self,
        name: str,
        handler: TestHandler[Input, Output],
        test_case_parts: Dict[str, TestPart],
        config: Optional[Eth2Config],
    ) -> None:
        self.name = name
        self.handler = handler
        self.test_case_parts = test_case_parts
        self.config = config

        self.metadata = self._load_metadata()
        self._process_meta(self.metadata)

    def _load_metadata(self) -> Dict[str, Any]:
        if META_KEY not in self.test_case_parts:
            return {}

        metadata_test_part = self.test_case_parts[META_KEY]
        return metadata_test_part.load()

    def _process_meta(self, metadata: Dict[str, Any]) -> None:
        self.bls_setting = BLSSetting(metadata.get(BLS_SETTING_KEY, 0))

    def valid(self) -> bool:
        return self.handler.valid(self.test_case_parts)

    def execute(self) -> None:
        _select_bls_backend(self.bls_setting)
        inputs = self.handler.parse_inputs(self.test_case_parts, self.metadata)
        outputs = self.handler.run_with(inputs, self.config)

        # NOTE: parse outputs after running the handler as we may trigger
        # an exception due to an invalid test case that should raise before
        # invalid decoding of empty output we expect to be missing.
        expected_outputs = self.handler.parse_outputs(self.test_case_parts)

        self.handler.condition(outputs, expected_outputs)
