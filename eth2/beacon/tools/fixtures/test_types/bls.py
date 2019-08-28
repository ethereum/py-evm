from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Type, Union, cast

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
from eth2.beacon.tools.fixtures.test_handler import Input, Output, TestHandler
from eth2.configs import Eth2Config

from . import TestType

SequenceOfBLSPubkey = Tuple[BLSPubkey, ...]
SequenceOfBLSSignature = Tuple[BLSSignature, ...]
SignatureDescriptor = Dict[str, Union[int, bytes]]


class AggregatePubkeysHandler(TestHandler[SequenceOfBLSPubkey, BLSPubkey]):
    name = "aggregate_pubkeys"

    @classmethod
    def parse_inputs(_cls, test_case_data: Dict[str, Any]) -> SequenceOfBLSPubkey:
        return get_input_bls_pubkeys(test_case_data)["pubkeys"]

    @staticmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> BLSPubkey:
        return get_output_bls_pubkey(test_case_data)

    @classmethod
    def run_with(_cls, inputs: SequenceOfBLSPubkey, _config: Eth2Config) -> BLSPubkey:
        # BLS override
        bls.use(MilagroBackend)

        return bls.aggregate_pubkeys(inputs)

    @staticmethod
    def condition(output: BLSPubkey, expected_output: BLSPubkey) -> None:
        assert output == expected_output


class AggregateSignaturesHandler(TestHandler[SequenceOfBLSSignature, BLSSignature]):
    name = "aggregate_sigs"

    @classmethod
    def parse_inputs(_cls, test_case_data: Dict[str, Any]) -> SequenceOfBLSSignature:
        return get_input_bls_signatures(test_case_data)["signatures"]

    @staticmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> BLSSignature:
        return get_output_bls_signature(test_case_data)

    @classmethod
    def run_with(
        _cls, inputs: SequenceOfBLSSignature, _config: Eth2Config
    ) -> BLSSignature:
        # BLS override
        bls.use(MilagroBackend)

        return bls.aggregate_signatures(inputs)

    @staticmethod
    def condition(output: BLSSignature, expected_output: BLSSignature) -> None:
        assert output == expected_output


class PrivateToPublicKeyHandler(TestHandler[int, BLSPubkey]):
    name = "priv_to_pub"

    @classmethod
    def parse_inputs(_cls, test_case_data: Dict[str, Any]) -> int:
        return get_input_bls_privkey(test_case_data)["privkey"]

    @staticmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> BLSPubkey:
        return get_output_bls_pubkey(test_case_data)

    @classmethod
    def run_with(_cls, inputs: int, _config: Eth2Config) -> BLSPubkey:
        # BLS override
        bls.use(MilagroBackend)

        return bls.privtopub(inputs)

    @staticmethod
    def condition(output: BLSPubkey, expected_output: BLSPubkey) -> None:
        assert output == expected_output


class SignMessageHandler(TestHandler[SignatureDescriptor, BLSSignature]):
    name = "sign_msg"

    @classmethod
    def parse_inputs(_cls, test_case_data: Dict[str, Any]) -> SignatureDescriptor:
        return get_input_sign_message(test_case_data)

    @staticmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> BLSSignature:
        return get_output_bls_signature(test_case_data)

    @classmethod
    def run_with(
        _cls, inputs: SignatureDescriptor, _config: Eth2Config
    ) -> BLSSignature:
        # BLS override
        bls.use(MilagroBackend)

        return bls.sign(
            cast(Hash32, inputs["message_hash"]),
            int(inputs["privkey"]),
            cast(Domain, (inputs["domain"])),
        )

    @staticmethod
    def condition(output: BLSSignature, expected_output: BLSSignature) -> None:
        assert output == expected_output


BLSHandlerType = Tuple[
    Type[AggregatePubkeysHandler],
    Type[AggregateSignaturesHandler],
    Type[PrivateToPublicKeyHandler],
    Type[SignMessageHandler],
]


class BLSTestType(TestType[BLSHandlerType]):
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
        test_handler: TestHandler[Input, Output],
        config_type: Optional[ConfigType],
    ) -> Path:
        file_name = f"{test_handler.name}.yaml"

        return (
            tests_root_path / Path(cls.name) / Path(test_handler.name) / Path(file_name)
        )
