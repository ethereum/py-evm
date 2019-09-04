from typing import Any, Dict, Optional, Tuple, Type, Union, cast

from eth_utils import decode_hex
from py_ecc.bls.typing import Domain

from eth2._utils.bls import BLSPubkey, BLSSignature, Hash32, bls
from eth2._utils.bls.backends import MilagroBackend
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.tools.fixtures.test_part import TestPart
from eth2.configs import Eth2Config

from . import TestType

SequenceOfBLSPubkey = Tuple[BLSPubkey, ...]
SequenceOfBLSSignature = Tuple[BLSSignature, ...]
SignatureDescriptor = Dict[str, Union[int, bytes]]


def get_input_bls_pubkeys(
    test_case: Dict[str, Any]
) -> Dict[str, Tuple[BLSPubkey, ...]]:
    return {
        "pubkeys": tuple(BLSPubkey(decode_hex(item)) for item in test_case["input"])
    }


def get_input_bls_signatures(
    test_case: Dict[str, Any]
) -> Dict[str, Tuple[BLSSignature, ...]]:
    return {
        "signatures": tuple(
            BLSSignature(decode_hex(item)) for item in test_case["input"]
        )
    }


def get_input_bls_privkey(test_case: Dict[str, Any]) -> Dict[str, int]:
    return {"privkey": int.from_bytes(decode_hex(test_case["input"]), "big")}


def get_input_sign_message(test_case: Dict[str, Any]) -> Dict[str, Union[int, bytes]]:
    return {
        "privkey": int.from_bytes(decode_hex(test_case["input"]["privkey"]), "big"),
        "message_hash": decode_hex(test_case["input"]["message"]),
        "domain": decode_hex(test_case["input"]["domain"]),
    }


def get_output_bls_pubkey(test_case: Dict[str, Any]) -> BLSPubkey:
    return BLSPubkey(decode_hex(test_case["output"]))


def get_output_bls_signature(test_case: Dict[str, Any]) -> BLSSignature:
    return BLSSignature(decode_hex(test_case["output"]))


class AggregatePubkeysHandler(TestHandler[SequenceOfBLSPubkey, BLSPubkey]):
    name = "aggregate_pubkeys"

    @classmethod
    def parse_inputs(
        _cls, test_case_parts: Dict[str, TestPart], metadata: Dict[str, Any]
    ) -> SequenceOfBLSPubkey:
        test_case_data = test_case_parts["data"].load()
        return get_input_bls_pubkeys(test_case_data)["pubkeys"]

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, TestPart]) -> BLSPubkey:
        test_case_data = test_case_parts["data"].load()
        return get_output_bls_pubkey(test_case_data)

    @classmethod
    def run_with(
        _cls, inputs: SequenceOfBLSPubkey, _config: Optional[Eth2Config]
    ) -> BLSPubkey:
        # BLS override
        bls.use(MilagroBackend)

        return bls.aggregate_pubkeys(inputs)

    @staticmethod
    def condition(output: BLSPubkey, expected_output: BLSPubkey) -> None:
        assert output == expected_output


class AggregateSignaturesHandler(TestHandler[SequenceOfBLSSignature, BLSSignature]):
    name = "aggregate_sigs"

    @classmethod
    def parse_inputs(
        _cls, test_case_parts: Dict[str, TestPart], metadata: Dict[str, Any]
    ) -> SequenceOfBLSSignature:
        test_case_data = test_case_parts["data"].load()
        return get_input_bls_signatures(test_case_data)["signatures"]

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, TestPart]) -> BLSSignature:
        test_case_data = test_case_parts["data"].load()
        return get_output_bls_signature(test_case_data)

    @classmethod
    def run_with(
        _cls, inputs: SequenceOfBLSSignature, _config: Optional[Eth2Config]
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
    def parse_inputs(
        _cls, test_case_parts: Dict[str, TestPart], metadata: Dict[str, Any]
    ) -> int:
        test_case_data = test_case_parts["data"].load()
        return get_input_bls_privkey(test_case_data)["privkey"]

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, TestPart]) -> BLSPubkey:
        test_case_data = test_case_parts["data"].load()
        return get_output_bls_pubkey(test_case_data)

    @classmethod
    def run_with(_cls, inputs: int, _config: Optional[Eth2Config]) -> BLSPubkey:
        # BLS override
        bls.use(MilagroBackend)

        return bls.privtopub(inputs)

    @staticmethod
    def condition(output: BLSPubkey, expected_output: BLSPubkey) -> None:
        assert output == expected_output


class SignMessageHandler(TestHandler[SignatureDescriptor, BLSSignature]):
    name = "sign_msg"

    @classmethod
    def parse_inputs(
        _cls, test_case_parts: Dict[str, TestPart], metadata: Dict[str, Any]
    ) -> SignatureDescriptor:
        test_case_data = test_case_parts["data"].load()
        return get_input_sign_message(test_case_data)

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, TestPart]) -> BLSSignature:
        test_case_data = test_case_parts["data"].load()
        return get_output_bls_signature(test_case_data)

    @classmethod
    def run_with(
        _cls, inputs: SignatureDescriptor, _config: Optional[Eth2Config]
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
