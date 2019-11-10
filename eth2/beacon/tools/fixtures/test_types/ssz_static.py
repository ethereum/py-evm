from typing import Any, Dict, Optional, Tuple, Type

from eth_typing import Hash32
import ssz
from ssz.tools import from_formatted_dict

from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.tools.fixtures.test_part import TestPart
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestations import Attestation, IndexedAttestation
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.block_headers import BeaconBlockHeader
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody
from eth2.beacon.types.checkpoints import Checkpoint
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.historical_batch import HistoricalBatch
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.types.voluntary_exits import VoluntaryExit
from eth2.configs import Eth2Config

from . import TestType

InputType = Tuple[bytes, ssz.Serializable]
OutputType = Tuple[bytes, ssz.Serializable, bytes, Tuple[Hash32, Optional[Hash32]]]


def _deserialize_object_from_dict(
    data: Dict[str, Any], object_type: ssz.Serializable
) -> ssz.Serializable:
    if object_type == BeaconState:
        # NOTE: borrowing from `py-ssz`
        parse_args = tuple(
            data[field_name] for field_name in object_type._meta.field_names
        )
        input_args = from_formatted_dict(parse_args, object_type._meta.container_sedes)
        input_kwargs = dict(zip(object_type._meta.field_names, input_args))
        # NOTE: we want to inject some additiona kwargs here,
        # due to non-standard (but still valid) SSZ inputs
        input_kwargs["validator_and_balance_length_check"] = False
        return object_type(**input_kwargs)
    else:
        return from_formatted_dict(data, object_type)


def _deserialize_object_from_yaml(
    test_case_data: TestPart, object_type: ssz.Serializable
) -> ssz.Serializable:
    yaml_data = test_case_data.load_yaml()
    return _deserialize_object_from_dict(yaml_data, object_type)


def _deserialize_object_from_bytes(
    data: bytes, object_type: ssz.Serializable
) -> ssz.Serializable:
    deserialized_fields = object_type._meta.container_sedes.deserialize(data)
    deserialized_field_dict = dict(
        zip(object_type._meta.field_names, deserialized_fields)
    )
    if object_type == BeaconState:
        # NOTE: we want to inject some additiona kwargs here,
        # due to non-standard (but still valid) SSZ inputs
        deserialized_field_dict["validator_and_balance_length_check"] = False
        return object_type(**deserialized_field_dict)
    else:
        return object_type(**deserialized_field_dict)


class SSZHandler(TestHandler[InputType, OutputType]):
    name: str
    object_type: ssz.Serializable

    @classmethod
    def parse_inputs(
        cls, test_case_parts: Dict[str, Any], metadata: Dict[str, Any]
    ) -> InputType:
        serialized_ssz_object = test_case_parts["serialized"].load_bytes()
        ssz_object_from_yaml = _deserialize_object_from_yaml(
            test_case_parts["value"], cls.object_type
        )
        return serialized_ssz_object, ssz_object_from_yaml

    @classmethod
    def parse_outputs(cls, test_case_parts: Dict[str, Any]) -> OutputType:
        serialized_ssz_object = test_case_parts["serialized"].load_bytes()
        ssz_object_from_yaml = _deserialize_object_from_yaml(
            test_case_parts["value"], cls.object_type
        )
        roots_yaml = test_case_parts["roots"].load_yaml()
        roots = (roots_yaml["root"], roots_yaml.get("signing_root", None))
        return (
            serialized_ssz_object,
            ssz_object_from_yaml,
            serialized_ssz_object,
            roots,
        )

    @classmethod
    def run_with(cls, inputs: InputType, config: Optional[Eth2Config]) -> OutputType:
        serialized_ssz_object, ssz_object_from_yaml = inputs
        deserialized_object = _deserialize_object_from_bytes(
            serialized_ssz_object, cls.object_type
        )
        return (
            cls.object_type.serialize(ssz_object_from_yaml),
            deserialized_object,
            cls.object_type.serialize(deserialized_object),
            (
                ssz.get_hash_tree_root(ssz_object_from_yaml),
                ssz_object_from_yaml.signing_root
                if isinstance(ssz_object_from_yaml, ssz.SignedSerializable)
                else None,
            ),
        )

    @staticmethod
    def condition(output: OutputType, expected_output: OutputType) -> None:
        """
        Check that:
          parsing YAML and SSZ serializing == input serialization
          deserializing the input serialization yields the object given by YAML
          deserializing and serializing the input yields the input (roundtrip)
          the root and signing root match the given values
        """
        object_serialization, deserialized_object, roundtrip_bytes, roots = output
        (
            expected_object_serialization,
            expected_deserialized_object,
            expected_roundtrip_bytes,
            expected_roots,
        ) = output
        assert object_serialization == expected_object_serialization
        assert deserialized_object == expected_deserialized_object
        assert roundtrip_bytes == expected_roundtrip_bytes
        assert roots == expected_roots


class AttestationHandler(SSZHandler):
    name = "Attestation"
    object_type = Attestation


class AttestationDataHandler(SSZHandler):
    name = "AttestationData"
    object_type = AttestationData


class AttesterSlashingHandler(SSZHandler):
    name = "AttesterSlashing"
    object_type = AttesterSlashing


class BeaconBlockHandler(SSZHandler):
    name = "BeaconBlock"
    object_type = BeaconBlock


class BeaconBlockBodyHandler(SSZHandler):
    name = "BeaconBlockBody"
    object_type = BeaconBlockBody


class BeaconBlockHeaderHandler(SSZHandler):
    name = "BeaconBlockHeader"
    object_type = BeaconBlockHeader


class BeaconStateHandler(SSZHandler):
    name = "BeaconState"
    object_type = BeaconState


class CheckpointHandler(SSZHandler):
    name = "Checkpoint"
    object_type = Checkpoint


class DepositHandler(SSZHandler):
    name = "Deposit"
    object_type = Deposit


class DepositDataHandler(SSZHandler):
    name = "DepositData"
    object_type = DepositData


class Eth1DataHandler(SSZHandler):
    name = "Eth1Data"
    object_type = Eth1Data


class ForkHandler(SSZHandler):
    name = "Fork"
    object_type = Fork


class HistoricalBatchHandler(SSZHandler):
    name = "HistoricalBatch"
    object_type = HistoricalBatch


class IndexedAttestationHandler(SSZHandler):
    name = "IndexedAttestation"
    object_type = IndexedAttestation


class PendingAttestationHandler(SSZHandler):
    name = "PendingAttestation"
    object_type = PendingAttestation


class ProposerSlashingHandler(SSZHandler):
    name = "ProposerSlashing"
    object_type = ProposerSlashing


class ValidatorHandler(SSZHandler):
    name = "Validator"
    object_type = Validator


class VoluntaryExitHandler(SSZHandler):
    name = "VoluntaryExit"
    object_type = VoluntaryExit


SSZStaticHandlerType = Tuple[
    Type[AttestationHandler],
    Type[AttestationDataHandler],
    Type[AttesterSlashingHandler],
    Type[BeaconBlockHandler],
    Type[BeaconBlockBodyHandler],
    Type[BeaconBlockHeaderHandler],
    Type[BeaconStateHandler],
    Type[CheckpointHandler],
    Type[DepositHandler],
    Type[DepositDataHandler],
    Type[Eth1DataHandler],
    Type[ForkHandler],
    Type[HistoricalBatchHandler],
    Type[IndexedAttestationHandler],
    Type[PendingAttestationHandler],
    Type[ProposerSlashingHandler],
    Type[ValidatorHandler],
    Type[VoluntaryExitHandler],
]


class SSZStaticTestType(TestType[SSZStaticHandlerType]):
    name = "ssz_static"

    handlers = (
        AttestationHandler,
        AttestationDataHandler,
        AttesterSlashingHandler,
        BeaconBlockHandler,
        BeaconBlockBodyHandler,
        BeaconBlockHeaderHandler,
        BeaconStateHandler,
        CheckpointHandler,
        DepositHandler,
        DepositDataHandler,
        Eth1DataHandler,
        ForkHandler,
        HistoricalBatchHandler,
        IndexedAttestationHandler,
        PendingAttestationHandler,
        ProposerSlashingHandler,
        ValidatorHandler,
        VoluntaryExitHandler,
    )
