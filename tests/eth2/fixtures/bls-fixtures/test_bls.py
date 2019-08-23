from typing import (
    Tuple,
)
from dataclasses import (
    dataclass,
)
import pytest

from py_ecc.bls.typing import Domain

from eth2._utils.bls import bls
from eth2._utils.bls.backends import (
    MilagroBackend,
)
from eth2.beacon.tools.fixtures.loading import (
    get_input_bls_privkey,
    get_input_bls_pubkeys,
    get_input_bls_signatures,
    get_input_sign_message,
    get_output_bls_pubkey,
    get_output_bls_signature,
)
from eth2.beacon.tools.fixtures.test_case import (
    BaseTestCase,
)
from eth_typing import (
    BLSPubkey,
    BLSSignature,
    Hash32,
)


from tests.eth2.fixtures.helpers import (
    get_test_cases,
)
from tests.eth2.fixtures.path import (
    BASE_FIXTURE_PATH,
    ROOT_PROJECT_DIR,
)


# Test files
RUNNER_FIXTURE_PATH = BASE_FIXTURE_PATH / 'bls'
HANDLER_FIXTURE_PATHES = (
    RUNNER_FIXTURE_PATH / 'aggregate_pubkeys',
    RUNNER_FIXTURE_PATH / 'aggregate_sigs',
    # RUNNER_FIXTURE_PATH / 'msg_hash_g2_compressed',  # NOTE: No public API in PyEECBackend
    # RUNNER_FIXTURE_PATH / 'msg_hash_g2_uncompressed',  # NOTE: No public API in PyEECBackend
    RUNNER_FIXTURE_PATH / 'priv_to_pub',
    RUNNER_FIXTURE_PATH / 'sign_msg',
)
FILTERED_CONFIG_NAMES = ()


#
#  Test format
#
@dataclass
class BLSPubkeyAggregationTestCase(BaseTestCase):
    input: Tuple[BLSPubkey, ...]
    output: BLSPubkey


@dataclass
class BLSSignaturesAggregationTestCase(BaseTestCase):
    input: Tuple[BLSPubkey, ...]
    output: BLSSignature


@dataclass
class BLSPrivToPubTestCase(BaseTestCase):
    input: int
    output: BLSPubkey


@dataclass
class BLSSignMessageTestCase(BaseTestCase):
    input: Tuple[bytes, Hash32, Domain]
    output: BLSPubkey


handler_to_processing_call_map = {
    'aggregate_pubkeys': (
        bls.aggregate_pubkeys,
        BLSPubkeyAggregationTestCase,
        get_input_bls_pubkeys,
        get_output_bls_pubkey,
    ),
    'aggregate_sigs': (
        bls.aggregate_signatures,
        BLSSignaturesAggregationTestCase,
        get_input_bls_signatures,
        get_output_bls_signature,
    ),
    'priv_to_pub': (
        bls.privtopub,
        BLSPrivToPubTestCase,
        get_input_bls_privkey,
        get_output_bls_pubkey,
    ),
    'sign_msg': (
        bls.sign,
        BLSSignMessageTestCase,
        get_input_sign_message,
        get_output_bls_pubkey,
    ),
}


#
# Helpers for generating test suite
#
def parse_bls_test_case(test_case, handler, index, config=None):
    _, test_case_class, input_fn, output_fn = handler_to_processing_call_map[handler]
    return test_case_class(
        handler=handler,
        index=index,
        input=input_fn(test_case),
        output=output_fn(test_case),
    )


all_test_cases = get_test_cases(
    root_project_dir=ROOT_PROJECT_DIR,
    fixture_pathes=HANDLER_FIXTURE_PATHES,
    config_names=FILTERED_CONFIG_NAMES,
    parse_test_case_fn=parse_bls_test_case,
)


@pytest.mark.parametrize(
    "test_case, config",
    all_test_cases
)
def test_aggregate_pubkeys_fixture(config, test_case):
    bls.use(MilagroBackend)
    processing_call, _, _, _ = handler_to_processing_call_map[test_case.handler]
    assert processing_call(**(test_case.input)) == test_case.output
