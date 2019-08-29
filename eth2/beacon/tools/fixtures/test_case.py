from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from eth2._utils.bls import bls
from eth2._utils.bls.backends import MilagroBackend
from eth2.configs import Eth2Config

from .test_handler import Input, Output, TestHandler


class BLSSetting(Enum):
    Optional = 0
    Enabled = 1
    Disabled = 2


def _select_bls_backend(bls_setting: BLSSetting) -> None:
    if bls_setting == BLSSetting.Disabled:
        bls.use_noop_backend()
    elif bls_setting == BLSSetting.Enabled:
        bls.use(MilagroBackend)
    elif bls_setting == BLSSetting.Optional:
        # do not verify BLS to save time
        bls.use_noop_backend()


# META_KEY is the prefix of the filename of the YAML file storing metadata about a test case.
# e.g. in the context of a test case file tree, there is a file `meta.yaml`.
META_KEY = "meta"

BLS_SETTING_KEY = "bls_setting"


class TestCase:
    name: str
    handler: TestHandler[Input, Output]
    test_case_parts: Dict[str, Dict[str, Any]]
    config: Eth2Config

    def __init__(
        self,
        name,
        handler: TestHandler[Input, Output],
        test_case_parts: Dict[str, Dict[str, Any]],
        config: Eth2Config,
    ) -> None:
        self.name = name
        self.handler = handler
        self.test_case_parts = test_case_parts
        self.config = config

        self._process_meta(self.test_case_parts.get(META_KEY, {}))

    def _process_meta(self, metadata: Dict[str, Any]) -> None:
        self.bls_setting = BLSSetting(metadata.get(BLS_SETTING_KEY, 0))

    def valid(self) -> bool:
        return self.handler.valid(self.test_case_data)

    def execute(self) -> None:
        _select_bls_backend(self.bls_setting)
        inputs = self.handler.parse_inputs(self.test_case_parts)
        outputs = self.handler.run_with(inputs, self.config)
        expected_outputs = self.handler.parse_outputs(self.test_case_parts)
        self.handler.condition(outputs, expected_outputs)
