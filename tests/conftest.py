from pathlib import (
    Path,
)

from eth_keys import (
    keys,
)
from eth_utils import (
    decode_hex,
    setup_DEBUG2_logging,
    to_tuple,
    to_wei,
)
import pytest
import rlp

from eth import (
    constants,
)
from eth.chains.base import (
    Chain,
    MiningChain,
)
from eth.consensus import (
    PowConsensus,
)
from eth.consensus.noproof import (
    NoProofConsensus,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.vm.forks import (
    ArrowGlacierVM,
    BerlinVM,
    ByzantiumVM,
    ConstantinopleVM,
    FrontierVM,
    GrayGlacierVM,
    HomesteadVM,
    IstanbulVM,
    LondonVM,
    MuirGlacierVM,
    PetersburgVM,
    SpuriousDragonVM,
    TangerineWhistleVM,
)

#
#  Setup DEBUG2 level logging.
#
# This needs to be done before the other imports
setup_DEBUG2_logging()

# Uncomment this to have logs from tests written to a file.  This is useful for
# debugging when you need to dump the VM output from test runs.
"""
import datetime
import logging
import os
from eth_utils.logging import DEBUG2_LEVEL_NUM

@pytest.yield_fixture(autouse=True)
def _file_logging(request):

    logger = logging.getLogger('eth')

    level = DEBUG2_LEVEL_NUM
    #level = logging.DEBUG
    #level = logging.INFO

    logger.setLevel(level)

    fixture_data = request.getfuncargvalue('fixture_data')
    fixture_path = fixture_data[0]
    logfile_name = 'logs/{0}-{1}.log'.format(
        '-'.join(
            [os.path.basename(fixture_path)] +
            [str(value) for value in fixture_data[1:]]
        ),
        datetime.datetime.now().isoformat(),
    )

    with open(logfile_name, 'w') as logfile:
        handler = logging.StreamHandler(logfile)
        logger.addHandler(handler)
        try:
            yield logger
        finally:
            logger.removeHandler(handler)
"""


@pytest.fixture(
    params=[
        FrontierVM,
        HomesteadVM.configure(
            support_dao_fork=False,
        ),
        TangerineWhistleVM,
        SpuriousDragonVM,
        ByzantiumVM,
        ConstantinopleVM,
        PetersburgVM,
        IstanbulVM,
        MuirGlacierVM,
        BerlinVM,
        LondonVM,
        ArrowGlacierVM,
        GrayGlacierVM,
    ]
)
def VM(request):
    return request.param


@pytest.fixture
def base_db():
    return AtomicDB()


@pytest.fixture
def funded_address_private_key():
    return keys.PrivateKey(
        decode_hex("0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8")
    )


@pytest.fixture
def funded_address(funded_address_private_key):
    return funded_address_private_key.public_key.to_canonical_address()


@pytest.fixture
def funded_address_initial_balance():
    return to_wei(1000, "ether")


# wrapped in a method so that different callers aren't using (and modifying)
# the same dict
def _get_genesis_defaults():
    # values that are not yet customizeable (and will automatically be default)
    # are commented out
    return {
        "difficulty": constants.GENESIS_DIFFICULTY,
        "gas_limit": 3141592,
        "coinbase": constants.GENESIS_COINBASE,
        "nonce": constants.GENESIS_NONCE,
        "mix_hash": constants.GENESIS_MIX_HASH,
        "extra_data": constants.GENESIS_EXTRA_DATA,
        "timestamp": 1501851927,
        # 'block_number': constants.GENESIS_BLOCK_NUMBER,
        # 'parent_hash': constants.GENESIS_PARENT_HASH,
        # "bloom": 0,
        # "gas_used": 0,
        # "uncles_hash": decode_hex("1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347")  # noqa: E501
        # "receipt_root": decode_hex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"),  # noqa: E501
        # "transaction_root": decode_hex("56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"),  # noqa: E501
    }


def _chain_with_block_validation(VM, base_db, genesis_state, chain_cls=Chain):
    """
    Return a Chain object containing just the genesis block.

    The Chain's state includes one funded account, which can be found in the
    funded_address in the chain itself.

    This Chain will perform all validations when importing new blocks, so only
    valid and finalized blocks can be used with it. If you want to test
    importing arbitrarily constructe, not finalized blocks, use the
    chain_without_block_validation fixture instead.
    """
    klass = chain_cls.configure(
        __name__="TestChain",
        vm_configuration=(
            (
                constants.GENESIS_BLOCK_NUMBER,
                VM.configure(consensus_class=PowConsensus),
            ),
        ),
        chain_id=1337,
    )
    chain = klass.from_genesis(base_db, _get_genesis_defaults(), genesis_state)
    return chain


@pytest.fixture
def chain_with_block_validation(VM, base_db, genesis_state):
    return _chain_with_block_validation(VM, base_db, genesis_state)


@pytest.fixture(scope="function")
def chain_from_vm(request, base_db, genesis_state):
    """
    This fixture is to be used only when the properties of the
    chains differ from one VM to another.
    For example, the block rewards change from one VM chain to another
    """

    def get_chain_from_vm(vm):
        return _chain_with_block_validation(vm, base_db, genesis_state)

    return get_chain_from_vm


def import_block_without_validation(chain, block):
    return super(type(chain), chain).import_block(block, perform_validation=False)


@pytest.fixture
def base_genesis_state(funded_address, funded_address_initial_balance):
    return {
        funded_address: {
            "balance": funded_address_initial_balance,
            "nonce": 0,
            "code": b"",
            "storage": {},
        }
    }


@pytest.fixture
def genesis_state(base_genesis_state):
    return base_genesis_state


def _chain_without_block_validation(request, VM, base_db, genesis_state):
    """
    Return a Chain object containing just the genesis block.

    This Chain does not perform any validation when importing new blocks.

    The Chain's state includes one funded account and a private key for it,
    which can be found in the funded_address and private_keys variables in the
    chain itself.
    """
    # Disable block validation so that we don't need to construct finalized blocks.
    overrides = {
        "import_block": import_block_without_validation,
        "validate_block": lambda self, block: None,
    }
    chain_class = request.param
    klass = chain_class.configure(
        __name__="TestChainWithoutBlockValidation",
        vm_configuration=(
            (
                constants.GENESIS_BLOCK_NUMBER,
                VM.configure(consensus_class=NoProofConsensus),
            ),
        ),
        chain_id=1337,
        **overrides,
    )
    chain = klass.from_genesis(base_db, _get_genesis_defaults(), genesis_state)
    return chain


@pytest.fixture(params=[Chain, MiningChain])
def chain_without_block_validation(request, VM, base_db, genesis_state):
    return _chain_without_block_validation(request, VM, base_db, genesis_state)


@pytest.fixture(params=[Chain, MiningChain])
def chain_without_block_validation_factory(request, VM, genesis_state):
    return lambda db: _chain_without_block_validation(request, VM, db, genesis_state)


@pytest.fixture(params=[Chain, MiningChain])
def chain_without_block_validation_from_vm(request, base_db, genesis_state):
    """
    This fixture is to be used only when the properties of the
    chains differ from one VM to another.
    For example, the block rewards change from one VM chain to another
    """

    def get_chain_from_vm(vm):
        return _chain_without_block_validation(request, vm, base_db, genesis_state)

    return get_chain_from_vm


def pytest_addoption(parser):
    parser.addoption("--fork", type=str, required=False)


@to_tuple
def load_bytes_from_file(path):
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            else:
                yield decode_hex(line.strip())


@to_tuple
def deserialize_rlp_objects(serialized_objects, rlp_class):
    for encoded in serialized_objects:
        decoded = rlp.decode(encoded)
        yield rlp_class.deserialize(decoded)


@pytest.fixture
def ropsten_epoch_headers():
    rlp_path = Path(__file__).parent / "rlp-fixtures" / "ropston_epoch_headers.rlp"
    encoded_headers = load_bytes_from_file(rlp_path)
    return deserialize_rlp_objects(encoded_headers, BlockHeader)
