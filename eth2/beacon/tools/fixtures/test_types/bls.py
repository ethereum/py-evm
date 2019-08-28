from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from py_ecc.bls.typing import Domain

from eth2._utils.bls import BLSPubkey, BLSSignature, Hash32, bls
from eth2._utils.bls.backends import MilagroBackend
from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.loading import (
    get_input_bls_privkey,
    get_input_bls_pubkeys,
    get_input_bls_signatures,
    get_input_sign_message,
    get_output_bls_pubkey,
    get_output_bls_signature,
)
from eth2.beacon.tools.fixtures.test_handler import TestHandler

from . import TestType


class AggregatePubkeysHandler(TestHandler):
    name = "aggregate_pubkeys"

    def parse_inputs(self, test_case_data: Dict[str, Any]) -> Tuple[BLSPubkey, ...]:
        return get_input_bls_pubkeys(test_case_data)["pubkeys"]

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BLSPubkey:
        return get_output_bls_pubkey(test_case_data)

    def run_with(self, inputs: Tuple[BLSPubkey, ...], _config: None) -> BLSPubkey:
        # BLS override
        bls.use(MilagroBackend)

        return bls.aggregate_pubkeys(inputs)

    def condition(self, output: BLSPubkey, expected_output: BLSPubkey) -> None:
        assert output == expected_output


class AggregateSignaturesHandler(TestHandler):
    name = "aggregate_sigs"

    def parse_inputs(self, test_case_data: Dict[str, Any]) -> Tuple[BLSSignature, ...]:
        return get_input_bls_signatures(test_case_data)["signatures"]

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BLSSignature:
        return get_output_bls_signature(test_case_data)

    def run_with(self, inputs: Tuple[BLSSignature, ...], _config: None) -> BLSSignature:
        # BLS override
        bls.use(MilagroBackend)

        return bls.aggregate_signatures(inputs)

    def condition(self, output: BLSSignature, expected_output: BLSSignature) -> None:
        assert output == expected_output


class PrivateToPublicKeyHandler(TestHandler):
    name = "priv_to_pub"

    def parse_inputs(self, test_case_data: Dict[str, Any]) -> int:
        return get_input_bls_privkey(test_case_data)["privkey"]

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BLSPubkey:
        return get_output_bls_pubkey(test_case_data)

    def run_with(self, inputs: int, _config: None) -> BLSPubkey:
        # BLS override
        bls.use(MilagroBackend)

        return bls.privtopub(inputs)

    def condition(self, output: BLSPubkey, expected_output: BLSPubkey) -> None:
        assert output == expected_output


class SignMessageHandler(TestHandler):
    name = "sign_msg"

    def parse_inputs(
        self, test_case_data: Dict[str, Any]
    ) -> Tuple[bytes, Hash32, Domain]:
        return get_input_sign_message(test_case_data)

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BLSSignature:
        return get_output_bls_signature(test_case_data)

    def run_with(self, inputs: int, _config: None) -> BLSPubkey:
        # BLS override
        bls.use(MilagroBackend)

        return bls.sign(**inputs)

    def condition(self, output: BLSSignature, expected_output: BLSSignature) -> None:
        assert output == expected_output


class BLSTestType(TestType):
    name = "bls"

    handlers = (
        AggregatePubkeysHandler,
        AggregateSignaturesHandler,
        # MsgHashG2CompressedHandler, # NOTE: not exposed via public API in py_ecc
        # MsgHashG2UncompressedHandler, # NOTE: not exposed via public API in py_ecc
        PrivateToPublicKeyHandler,
        SignMessageHandler,
    )

    @classmethod
    def build_path(
        cls,
        tests_root_path: Path,
        test_handler: TestHandler,
        config_type: Optional[ConfigType],
    ) -> Path:
        file_name = f"{test_handler.name}.yaml"

        return (
            tests_root_path / Path(cls.name) / Path(test_handler.name) / Path(file_name)
        )
