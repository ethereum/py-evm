import json

import pytest

from eth_utils import ValidationError

from eth.chains.base import Chain
from eth.chains.mainnet import (
    HOMESTEAD_MAINNET_BLOCK,
    MainnetChain,
    MAINNET_GENESIS_HEADER,
)
from eth.chains.ropsten import RopstenChain, ROPSTEN_GENESIS_HEADER
from eth.db.atomic import AtomicDB
from eth.rlp.headers import BlockHeader
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


def test_mainnet_eip1085_rejects_etc_homestead_header(mainnet_genesis_config):
    PRE_FORK_HEADER = BlockHeader(
        difficulty=62382916183238,
        block_number=1919999,
        gas_limit=4707788,
        timestamp=1469020838,
        coinbase=b'*e\xac\xa4\xd5\xfc[\\\x85\x90\x90\xa6\xc3M\x16A59\x82&',
        parent_hash=b'P_\xfd!\xf4\xcb\xf2\xc5\xc3O\xa8L\xd8\xc9%%\xf3\xa7\x19\xb7\xad\x18\x85+\xff\xdd\xad`\x105\xf5\xf4',  # noqa: E501
        uncles_hash=b'\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G',  # noqa: E501
        state_root=b'\xfd\xf2\xfc\x04X\x0b\x95\xca\x15\xde\xfcc\x90\x80\xb9\x02\xe98\x92\xdc\xce(\x8b\xe0\xc1\xf7\xa7\xbb\xc7x$\x8b',  # noqa: E501
        transaction_root=b'V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!',  # noqa: E501
        receipt_root=b'V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!',  # noqa: E501
        bloom=0,
        gas_used=0,
        extra_data=b'DwarfPool',
        mix_hash=b'\xa0#\n\xf0\xa0\xd3\xd2\x97\xb7\xe8\xc2G=\x16;\x1e\xb0\xb1\xbb\xbbN\x9d\x93>_\xde\xa0\x85F\xb5nY',  # noqa: E501
        nonce=b"`\x83'\t\xc8\x97\x9d\xaa",
    )

    ETC_HEADER_AT_FORK = BlockHeader(
        difficulty=62413376722602,
        block_number=1920000,
        gas_limit=4712384,
        timestamp=1469020839,
        coinbase=b'a\xc8\x08\xd8*:\xc521u\r\xad\xc1<w{Y1\x0b\xd9',
        parent_hash=b'\xa2\x18\xe2\xc6\x11\xf2\x122\xd8W\xe3\xc8\xce\xcd\xcd\xf1\xf6_%\xa4G\x7f\x98\xf6\xf4~@c\x80\x7f#\x08',  # noqa: E501
        uncles_hash=b'\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G',  # noqa: E501
        state_root=b'aM}5\x8b\x03\xcb\xda\xf045)g;\xe2\n\xd4X\t\xd0$\x87\xf0#\xe0G\xef\xdc\xe9\xda\x8a\xff',  # noqa: E501
        transaction_root=b'\xd30h\xa7\xf2\x1b\xffP\x18\xa0\x0c\xa0\x8a5f\xa0k\xe4\x19m\xfe\x9e9\xf9nC\x15e\xa6\x19\xd4U',  # noqa: E501
        receipt_root=b'{\xda\x9a\xa6Yw\x80\x03v\x12\x91H\xcb\xfe\x89\xd3Z\x01m\xd5\x1c\x95\xd6\xe6\xdc\x1ev0}1Th',  # noqa: E501
        bloom=0,
        gas_used=84000,
        extra_data=b'\xe4\xb8\x83\xe5\xbd\xa9\xe7\xa5\x9e\xe4\xbb\x99\xe9\xb1\xbc',
        mix_hash=b'\xc5-\xaapT\xba\xbeQ[\x17\xee\x98T\x0c\x08\x89\xcf^\x15\x95\xc5\xddwIi\x97\xca\x84\xa6\x8c\x8d\xa1',  # noqa: E501
        nonce=b"\x05'j`\t\x80\x19\x9d",
    )

    ETH_HEADER_AT_FORK = BlockHeader(
        difficulty=62413376722602,
        block_number=1920000,
        gas_limit=4712384,
        timestamp=1469020840,
        coinbase=b'\xbc\xdf\xc3[\x86\xbe\xdfr\xf0\xcd\xa0F\xa3\xc1h)\xa2\xefA\xd1',
        parent_hash=b'\xa2\x18\xe2\xc6\x11\xf2\x122\xd8W\xe3\xc8\xce\xcd\xcd\xf1\xf6_%\xa4G\x7f\x98\xf6\xf4~@c\x80\x7f#\x08',  # noqa: E501
        uncles_hash=b'\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G',  # noqa: E501
        state_root=b'\xc5\xe3\x89Aa\x16\xe3il\xce\x82\xecE3\xcc\xe3>\xfc\xcb$\xce$Z\xe9TjK\x8f\r^\x9au',  # noqa: E501
        transaction_root=b'w\x01\xdf\x8e\x07\x16\x94RUM\x14\xaa\xdd{\xfa%mJ\x1d\x03U\xc1\xd1t\xab7>>-\n7C',  # noqa: E501
        receipt_root=b'&\xcf\x9d\x94"\xe9\xdd\x95\xae\xdcy\x14\xdbi\x0b\x92\xba\xb6\x90/R!\xd6&\x94\xa2\xfa]\x06_SK',  # noqa: E501
        bloom=0,
        gas_used=84000,
        extra_data=b'dao-hard-fork',
        mix_hash=b'[Z\xcb\xf4\xbf0_\x94\x8b\xd7\xbe\x17`G\xb2\x06#\xe1A\x7fuYsA\xa0Yr\x91e\xb9#\x97',  # noqa: E501
        nonce=b'\xbe\xde\x87 \x1d\xe4$&',
    )

    genesis_data = extract_genesis_data(mainnet_genesis_config)
    homestead_vm = dict(genesis_data.vm_configuration)[HOMESTEAD_MAINNET_BLOCK]

    # The VM we derive from mainnet.json should validate the ETH header at the fork
    homestead_vm.validate_header(ETH_HEADER_AT_FORK, PRE_FORK_HEADER, check_seal=True)

    # But it should reject the ETC header
    with pytest.raises(ValidationError, match='must have extra data 0x64616f2d686172642d666f726b'):
        homestead_vm.validate_header(ETC_HEADER_AT_FORK, PRE_FORK_HEADER, check_seal=True)


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
