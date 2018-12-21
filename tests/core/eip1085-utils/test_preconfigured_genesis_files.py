import json

import pytest

from eth.chains.base import Chain
from eth.chains.mainnet import MainnetChain, MAINNET_GENESIS_HEADER
from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
from eth.db.atomic import AtomicDB
from eth.vm.forks.homestead import HomesteadVM

from trinity.config import (
    MAINNET_EIP1085_PATH,
    ROPSTEN_EIP1085_PATH,
)
from trinity._utils.eip1085 import (
    validate_raw_eip1085_genesis_config,
    extract_genesis_data,
)


@pytest.fixture
def mainnet_genesis_config():
    with MAINNET_EIP1085_PATH.open() as mainnet_eip1085_file:
        mainnet_genesis_config = json.load(mainnet_eip1085_file)
    return mainnet_genesis_config


def test_mainnet_eip1085_validity(mainnet_genesis_config):
    validate_raw_eip1085_genesis_config(mainnet_genesis_config)


def test_mainnet_eip1085_matches_mainnet_genesis_header(mainnet_genesis_config):
    genesis_data = extract_genesis_data(mainnet_genesis_config)
    genesis_state = {
        address: account.to_dict()
        for address, account in genesis_data.state.items()
    }
    genesis_params = genesis_data.params.to_dict()
    chain = Chain.configure(
        vm_configuration=genesis_data.vm_configuration,
        chain_id=genesis_data.chain_id,
    ).from_genesis(AtomicDB(), genesis_params, genesis_state)
    genesis_header = chain.get_canonical_head()

    assert genesis_header == MAINNET_GENESIS_HEADER
    assert chain.chain_id == MainnetChain.chain_id

    actual_fork_blocks = tuple(zip(*chain.vm_configuration))[0]
    expected_fork_blocks = tuple(zip(*MainnetChain.vm_configuration))[0]

    assert actual_fork_blocks == expected_fork_blocks

    actual_homestead_vm = chain.vm_configuration[1][1]
    expected_homestead_vm = MainnetChain.vm_configuration[1][1]

    assert issubclass(actual_homestead_vm, HomesteadVM)
    assert actual_homestead_vm.support_dao_fork is True
    assert actual_homestead_vm.get_dao_fork_block_number() == expected_homestead_vm.get_dao_fork_block_number()  # noqa: E501


@pytest.fixture
def ropsten_genesis_config():
    with ROPSTEN_EIP1085_PATH.open() as ropsten_eip1085_file:
        ropsten_genesis_config = json.load(ropsten_eip1085_file)
    return ropsten_genesis_config


def test_ropsten_eip1085_validity(ropsten_genesis_config):
    validate_raw_eip1085_genesis_config(ropsten_genesis_config)


def test_ropsten_eip1085_matches_ropsten_chain(ropsten_genesis_config):
    genesis_data = extract_genesis_data(ropsten_genesis_config)
    genesis_state = {
        address: account.to_dict()
        for address, account in genesis_data.state.items()
    }
    genesis_params = genesis_data.params.to_dict()
    chain = Chain.configure(
        vm_configuration=genesis_data.vm_configuration,
        chain_id=genesis_data.chain_id,
    ).from_genesis(AtomicDB(), genesis_params, genesis_state)
    genesis_header = chain.get_canonical_head()

    assert genesis_header == ROPSTEN_GENESIS_HEADER
    assert chain.chain_id == RopstenChain.chain_id
    assert chain.vm_configuration == RopstenChain.vm_configuration
