import logging

import pytest

import rlp

from eth_tester.exceptions import (
    ValidationError,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from eth_utils import (
    keccak,
    to_canonical_address,
)

from evm.utils.address import (
    generate_contract_address,
)
from evm.utils.hexadecimal import (
    encode_hex,
)

from evm.chains.sharding.mainchain_handler import (
    vmc_utils,
)

from evm.chains.sharding.mainchain_handler.config import (
    PERIOD_LENGTH,
)

from evm.chains.sharding.mainchain_handler.mainchain_handler import (
    MainchainHandler,
)

from evm.chains.sharding.mainchain_handler.vmc_handler import (
    VMCHandler,
)

from tests.sharding.mainchain_handler.fixtures import (
    mainchain_handler,
)

PASSPHRASE = '123'
# for testing we set it to 5, 25 or 2500 originally
SHUFFLING_CYCLE_LENGTH = 5

test_keys = get_default_account_keys()

logger = logging.getLogger('evm.chain.sharding.mainchain_handler.VMCHandler')

def do_withdraw(vmc_handler, validator_index):
    assert validator_index < len(test_keys)
    privkey = test_keys[validator_index]
    sender_addr = privkey.public_key.to_canonical_address()
    signature = vmc_utils.sign(vmc_utils.WITHDRAW_HASH, privkey)
    vmc_handler.withdraw(validator_index, signature, sender_addr)
    vmc_handler.mainchain_handler.mine(1)

def deploy_valcode_and_deposit(vmc_handler, key):
    """
    Deploy validation code of and with the key, and do deposit

    :param key: Key object
    :return: returns nothing
    """
    address = key.public_key.to_canonical_address()
    vmc_handler.mainchain_handler.unlock_account(address, PASSPHRASE)
    valcode = vmc_utils.mk_validation_code(
        key.public_key.to_canonical_address()
    )
    nonce = vmc_handler.mainchain_handler.get_nonce(address)
    valcode_addr = generate_contract_address(to_canonical_address(address), nonce)
    vmc_handler.mainchain_handler.unlock_account(address, PASSPHRASE)
    vmc_handler.mainchain_handler.deploy_contract(valcode, address)
    vmc_handler.mainchain_handler.mine(1)
    vmc_handler.deposit(valcode_addr, address, address)

def deploy_initiating_contracts(vmc_handler, privkey):
    if not vmc_handler.is_vmc_deployed():
        address = privkey.public_key.to_canonical_address()
        vmc_handler.mainchain_handler.unlock_account(address, PASSPHRASE)
        nonce = vmc_handler.mainchain_handler.get_nonce(address)
        txs = vmc_utils.mk_initiating_contracts(privkey, nonce)
        for tx in txs[:3]:
            vmc_handler.mainchain_handler.direct_tx(tx)
        vmc_handler.mainchain_handler.mine(1)
        for tx in txs[3:]:
            vmc_handler.mainchain_handler.direct_tx(tx)
            vmc_handler.mainchain_handler.mine(1)
        logger.debug(
            'deploy_initiating_contracts: vmc_tx_hash=%s',
            vmc_handler.mainchain_handler.get_transaction_receipt(encode_hex(txs[-1].hash)),
        )

def first_setup_and_deposit(vmc_handler, key):
    deploy_valcode_and_deposit(vmc_handler, key)
    # TODO: error occurs when we don't mine so many blocks
    vmc_handler.mainchain_handler.mine(SHUFFLING_CYCLE_LENGTH)

def import_key_to_mainchain_handler(vmc_handler, key):
    """
    :param vmc_handler: VMCHandler
    :param privkey: PrivateKey object from eth_keys
    """
    try:
        vmc_handler.mainchain_handler.import_privkey(key, PASSPHRASE)
    # Exceptions happen when the key is already imported.
    #   - ValueError: `web3.py`
    #   - ValidationError: `eth_tester`
    except (ValueError, ValidationError):
        pass

def get_testing_colhdr(vmc_handler,
                       shard_id,
                       parent_collation_hash,
                       number,
                       collation_coinbase=test_keys[0].public_key.to_canonical_address(),
                       privkey=test_keys[0]):
    period_length = PERIOD_LENGTH
    expected_period_number = (vmc_handler.mainchain_handler.get_block_number() + 1) // period_length
    logger.debug("get_testing_colhdr: expected_period_number=%s", expected_period_number)
    period_start_prevhash = vmc_handler.get_period_start_prevhash(expected_period_number)
    logger.debug("get_testing_colhdr: period_start_prevhash=%s", period_start_prevhash)
    tx_list_root = b"tx_list " * 4
    post_state_root = b"post_sta" * 4
    receipt_root = b"receipt " * 4
    sighash = keccak(
        rlp.encode([
            shard_id,
            expected_period_number,
            period_start_prevhash,
            parent_collation_hash,
            tx_list_root,
            collation_coinbase,
            post_state_root,
            receipt_root,
            number,
        ])
    )
    sig = vmc_utils.sign(sighash, privkey)
    return rlp.encode([
        shard_id,
        expected_period_number,
        period_start_prevhash,
        parent_collation_hash,
        tx_list_root,
        collation_coinbase,
        post_state_root,
        receipt_root,
        number,
        sig,
    ])

def test_vmc_handler(mainchain_handler):
    shard_id = 0
    validator_index = 0
    primary_addr = test_keys[validator_index].public_key.to_canonical_address()
    zero_addr = b'\x00' * 20

    vmc_handler = VMCHandler(mainchain_handler, primary_addr=primary_addr)
    logger.debug("!@# viper_rlp_decoder_addr=%s", vmc_utils.viper_rlp_decoder_addr)
    logger.debug("!@# sighasher_addr=%s", vmc_utils.sighasher_addr)

    if not vmc_handler.is_vmc_deployed():
        logger.debug('handler.is_vmc_deployed() == True')
        # import privkey
        for key in test_keys:
            import_key_to_mainchain_handler(vmc_handler, key)

        deploy_initiating_contracts(vmc_handler, test_keys[validator_index])
        vmc_handler.mainchain_handler.mine(1)
        first_setup_and_deposit(vmc_handler, test_keys[validator_index])

    assert vmc_handler.is_vmc_deployed()

    vmc_handler.mainchain_handler.mine(SHUFFLING_CYCLE_LENGTH)

    assert vmc_handler.sample(shard_id) != zero_addr
    assert vmc_handler.get_num_validators() == 1
    logger.debug("vmc_handler.get_num_validators()=%s", vmc_handler.get_num_validators())

    genesis_colhdr_hash = b'\x00' * 32
    header1 = get_testing_colhdr(vmc_handler, shard_id, genesis_colhdr_hash, 1)
    header1_hash = keccak(header1)
    vmc_handler.add_header(header1, primary_addr)
    vmc_handler.mainchain_handler.mine(SHUFFLING_CYCLE_LENGTH)

    header2 = get_testing_colhdr(vmc_handler, shard_id, header1_hash, 2)
    header2_hash = keccak(header2)
    vmc_handler.add_header(header2, primary_addr)
    vmc_handler.mainchain_handler.mine(SHUFFLING_CYCLE_LENGTH)

    assert vmc_handler.get_collation_header_score(shard_id, header1_hash) == 1
    assert vmc_handler.get_collation_header_score(shard_id, header2_hash) == 2

    vmc_handler.tx_to_shard(
        test_keys[1].public_key.to_canonical_address(),
        shard_id,
        100000,
        1,
        b'',
        1234567,
        primary_addr,
    )
    vmc_handler.mainchain_handler.mine(1)
    assert vmc_handler.get_receipt_value(0) == 1234567

    do_withdraw(vmc_handler, validator_index)
    vmc_handler.mainchain_handler.mine(1)
    assert vmc_handler.sample(shard_id) == zero_addr
