import pytest

from eth_utils import (
    decode_hex,
    to_int,
)

from eth.db.atomic import AtomicDB
from eth.vm.forks.constantinople import ConstantinopleVM
from eth.vm.forks.homestead import HomesteadVM
from eth.chains.mainnet import (
    MainnetChain,
    MAINNET_GENESIS_HEADER,
)
from eth.chains.ropsten import (
    RopstenChain,
    ROPSTEN_GENESIS_HEADER,
)

from trinity.config import (
    Eth1ChainConfig,
)
from trinity.constants import (
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
)
from trinity._utils.db import MemoryDB
from trinity._utils.eip1085 import validate_raw_eip1085_genesis_config


def assert_vm_configuration_equal(left, right):
    assert len(left) == len(right), "Length mismatch"

    for ((left_block, left_vm), (right_block, right_vm)) in zip(left, right):
        assert left_vm.fork is not None
        assert left_vm.fork == right_vm.fork
        assert left_block == right_block

        if isinstance(left_vm, HomesteadVM):
            assert left_vm.support_dao_fork is right_vm.support_dao_fork
            assert left_vm.dao_fork_block_number == right_vm.dao_fork_block_number


@pytest.mark.parametrize(
    'network_id',
    (MAINNET_NETWORK_ID, ROPSTEN_NETWORK_ID),
)
def test_chain_config_from_preconfigured_network(network_id):
    chain_config = Eth1ChainConfig.from_preconfigured_network(network_id)
    chain = chain_config.initialize_chain(AtomicDB(MemoryDB()))

    if network_id == MAINNET_NETWORK_ID:
        assert chain_config.chain_id == MainnetChain.chain_id
        assert_vm_configuration_equal(chain_config.vm_configuration, MainnetChain.vm_configuration)
        assert chain.get_canonical_head() == MAINNET_GENESIS_HEADER
    elif network_id == ROPSTEN_NETWORK_ID:
        assert chain_config.chain_id == RopstenChain.chain_id
        assert_vm_configuration_equal(chain_config.vm_configuration, RopstenChain.vm_configuration)
        assert chain.get_canonical_head() == ROPSTEN_GENESIS_HEADER
    else:
        assert False, "Invariant: unreachable code path"


EIP1085_GENESIS_CONFIG = {
    "version": "1",
    "params": {
        "miningMethod": "NoProof",
        "homesteadForkBlock": "0x00",
        "EIP150ForkBlock": "0x00",
        "EIP158ForkBlock": "0x00",
        "byzantiumForkBlock": "0x00",
        "constantinopleForkBlock": "0x00",
        "chainId": "0x04d2",
    },
    "genesis": {
        "nonce": "0x0000000000000042",
        "difficulty": "0x020000",
        "author": "0x0000000000000000000000000000000000000000",
        "timestamp": "0x00",
        "extraData": "0x11bbe8db4e347b4e8c937c1c8370e4b5ed33adb3db69cbdb7a38e1e50b1b82fa",
        "gasLimit": "0x1388"
    }
}


def test_chain_config_eip1085_fixture_is_valid():
    # Sanity check in case this fixture is no longer actually valid against the
    # spec which has not been finalized at the time this was created.
    validate_raw_eip1085_genesis_config(EIP1085_GENESIS_CONFIG)


def test_chain_config_from_eip1085_genesis_config():
    chain_config = Eth1ChainConfig.from_eip1085_genesis_config(EIP1085_GENESIS_CONFIG)

    assert chain_config.chain_id == 1234
    assert chain_config.vm_configuration == ((0, ConstantinopleVM),)

    params = chain_config.genesis_params

    assert params.nonce == decode_hex(EIP1085_GENESIS_CONFIG['genesis']['nonce'])
    assert params.difficulty == to_int(hexstr=EIP1085_GENESIS_CONFIG['genesis']['difficulty'])
    assert params.coinbase == decode_hex(EIP1085_GENESIS_CONFIG['genesis']['author'])
    assert params.timestamp == to_int(hexstr=EIP1085_GENESIS_CONFIG['genesis']['timestamp'])
    assert params.extra_data == decode_hex(EIP1085_GENESIS_CONFIG['genesis']['extraData'])
    assert params.gas_limit == to_int(hexstr=EIP1085_GENESIS_CONFIG['genesis']['gasLimit'])
