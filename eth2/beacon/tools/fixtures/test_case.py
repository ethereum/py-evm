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


class TestCase:
    def __init__(
        self,
        index: int,
        test_case_data: Dict[str, Any],
        handler: TestHandler[Input, Output],
        config: Eth2Config,
    ) -> None:
        self.index = index
        self.description = test_case_data.get("description", "")
        self.bls_setting = BLSSetting(test_case_data.get("bls_setting", 0))
        self.config = config
        self.test_case_data = test_case_data
        self.handler = handler

    def valid(self) -> bool:
        return self.handler.valid(self.test_case_data)

    def execute(self) -> None:
        _select_bls_backend(self.bls_setting)
        inputs = self.handler.parse_inputs(self.test_case_data)
        outputs = self.handler.run_with(inputs, self.config)
        expected_outputs = self.handler.parse_outputs(self.test_case_data)
        self.handler.condition(outputs, expected_outputs)
