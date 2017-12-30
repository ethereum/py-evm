import logging
import time

import pytest

import rlp

from web3.exceptions import (
    BadFunctionCallOutput,
)

from eth_tester.exceptions import (
    ValidationError,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from eth_utils import (
    to_canonical_address,
    to_checksum_address,
)

from evm.utils.address import (
    generate_contract_address,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.keccak import (
    keccak,
)

from evm.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
)

from evm.chains.sharding.mainchain_handler import (
    vmc_utils,
)

from evm.chains.sharding.mainchain_handler.config import (
    GASPRICE,
    PERIOD_LENGTH,
    TX_GAS,
)

from tests.sharding.mainchain_handler.fixtures import (  # noqa: F401
    vmc,
)

PASSPHRASE = '123'
ZERO_ADDR = b'\x00' * 20
# for testing we set it to 5, 25 or 2500 originally
SHUFFLING_CYCLE_LENGTH = 5

test_keys = get_default_account_keys()

logger = logging.getLogger('evm.chain.sharding.mainchain_handler.VMCHandler')


def get_code(vmc_handler, address):
    return vmc_handler.web3.eth.getCode(to_checksum_address(address))


def get_nonce(vmc_handler, address):
    return vmc_handler.web3.eth.getTransactionCount(to_checksum_address(address))


def mine(vmc_handler, num_blocks):
    vmc_handler.web3.testing.mine(num_blocks)


def send_raw_transaction(vmc_handler, raw_transaction):
    w3 = vmc_handler.web3
    raw_transaction_bytes = rlp.encode(raw_transaction)
    raw_transaction_hex = w3.toHex(raw_transaction_bytes)
    transaction_hash = w3.eth.sendRawTransaction(raw_transaction_hex)
    return transaction_hash


def deploy_contract(vmc_handler, bytecode, privkey, value=0, gas=TX_GAS, gas_price=GASPRICE):
    w3 = vmc_handler.web3
    contract_transaction_dict = {
        'nonce': get_nonce(vmc_handler, privkey.public_key.to_canonical_address()),
        'to': b'',  # CREATE_CONTRACT_ADDRESS
        'data': encode_hex(bytecode),
        'value': value,
        'gas': gas,
        'gasPrice': gas_price,
        'chainId': None,
    }
    signed_transaction_dict = w3.eth.account.signTransaction(
        contract_transaction_dict,
        privkey.to_hex(),
    )
    tx_hash = w3.eth.sendRawTransaction(signed_transaction_dict['rawTransaction'])
    return tx_hash


def is_vmc_deployed(vmc_handler):
    return (
        get_code(vmc_handler, vmc_handler.address) != b'' and
        get_nonce(vmc_handler, vmc_handler.vmc_tx_sender_address) != 0
    )


def do_withdraw(vmc_handler, validator_index):
    assert validator_index < len(test_keys)
    privkey = test_keys[validator_index]
    signature = vmc_utils.sign(vmc_utils.WITHDRAW_HASH, privkey)
    vmc_handler.withdraw(validator_index, signature)
    mine(vmc_handler, 1)


def deploy_valcode_and_deposit(vmc_handler, privkey):
    """
    Deploy validation code of and with the privkey, and do deposit

    :param privkey: PrivateKey object
    :return: returns nothing
    """
    address = privkey.public_key.to_canonical_address()
    valcode = vmc_utils.mk_validation_code(
        privkey.public_key.to_canonical_address()
    )
    nonce = get_nonce(vmc_handler, address)
    valcode_addr = generate_contract_address(to_canonical_address(address), nonce)
    deploy_contract(vmc_handler, valcode, privkey)
    mine(vmc_handler, 1)
    vmc_handler.deposit(valcode_addr, address)
    return valcode_addr


def deploy_initiating_contracts(vmc_handler, privkey):
    w3 = vmc_handler.web3
    nonce = get_nonce(vmc_handler, privkey.public_key.to_canonical_address())
    txs = vmc_utils.mk_initiating_contracts(privkey, nonce, SpuriousDragonTransaction)
    for tx in txs[:3]:
        send_raw_transaction(vmc_handler, tx)
    mine(vmc_handler, 1)
    for tx in txs[3:]:
        send_raw_transaction(vmc_handler, tx)
        mine(vmc_handler, 1)
    logger.debug(
        'deploy_initiating_contracts: vmc_tx_hash=%s',
        w3.eth.getTransactionReceipt(encode_hex(txs[-1].hash)),
    )


def import_key(vmc_handler, privkey):
    """
    :param vmc_handler: VMCHandler
    :param privkey: PrivateKey object from eth_keys
    """
    try:
        vmc_handler.web3.personal.importRawKey(privkey.to_hex(), PASSPHRASE)
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
    current_block_number = vmc_handler.web3.eth.blockNumber
    expected_period_number = (current_block_number + 1) // period_length
    logger.debug("get_testing_colhdr: expected_period_number=%s", expected_period_number)
    sender_addr = privkey.public_key.to_canonical_address()
    period_start_prevhash = vmc_handler.call(
        vmc_handler.mk_contract_tx_detail(sender_address=sender_addr, gas=TX_GAS)
    ).get_period_start_prevhash(expected_period_number)
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


def test_vmc_contract_calls(vmc):  # noqa: F811
    shard_id = 0
    validator_index = 0
    primary_key = test_keys[validator_index]
    primary_addr = test_keys[validator_index].public_key.to_canonical_address()
    default_gas = TX_GAS

    # test `mk_build_transaction_detail` ######################################
    build_transaction_detail = vmc.mk_build_transaction_detail(
        nonce=0,
        gas=10000,
    )
    assert 'nonce' in build_transaction_detail
    assert 'gas' in build_transaction_detail
    assert 'chainId' in build_transaction_detail
    with pytest.raises(ValueError):
        build_transaction_detail = vmc.mk_build_transaction_detail(
            nonce=None,
            gas=10000,
        )
    with pytest.raises(ValueError):
        build_transaction_detail = vmc.mk_build_transaction_detail(
            nonce=0,
            gas=None,
        )

    # test `mk_contract_tx_detail` ######################################
    tx_detail = vmc.mk_contract_tx_detail(
        sender_address=ZERO_ADDR,
        gas=TX_GAS,
    )
    assert 'from' in tx_detail
    assert 'gas' in tx_detail
    with pytest.raises(ValueError):
        tx_detail = vmc.mk_contract_tx_detail(
            sender_address=ZERO_ADDR,
            gas=None,
        )
    with pytest.raises(ValueError):
        tx_detail = vmc.mk_contract_tx_detail(
            sender_address=None,
            gas=TX_GAS,
        )

    # test the deployment of vmc ######################################
    # deploy vmc if it is not deployed yet.
    if not is_vmc_deployed(vmc):
        logger.debug('is_vmc_deployed(vmc) == True')
        # import test_key
        import_key(vmc, primary_key)
        deploy_initiating_contracts(vmc, primary_key)
        mine(vmc, 1)
    assert is_vmc_deployed(vmc)

    # test `deposit` and `sample` ######################################
    # now we require 1 validator.
    # if there is currently no validator, we deposit one.
    # else, there should only be one validator, for easier testing.
    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_num_validators()
    if num_validators == 0:
        # deploy valcode for the validator, and deposit as the first validator
        valcode_addr = deploy_valcode_and_deposit(
            vmc,
            primary_key,
        )
        # TODO: error occurs when we don't mine so many blocks
        mine(vmc, SHUFFLING_CYCLE_LENGTH)
        assert vmc.sample(shard_id) == valcode_addr
    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_num_validators()
    assert num_validators == 1
    assert vmc.sample(shard_id) != ZERO_ADDR
    logger.debug("vmc_handler.get_num_validators()=%s", num_validators)

    # test `add_header` ######################################
    genesis_colhdr_hash = b'\x00' * 32
    # create a testing collation header, whose parent is the genesis
    header1 = get_testing_colhdr(vmc, shard_id, genesis_colhdr_hash, 1)
    header1_hash = keccak(header1)
    # if a header is added before its parent header is added, `add_header` should fail
    # BadFunctionCallOutput raised when assertions fail
    with pytest.raises(BadFunctionCallOutput):
        header_parent_not_added = get_testing_colhdr(
            vmc,
            shard_id,
            header1_hash,
            1,
        )
        vmc.call(vmc.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=default_gas,
            gas_price=1,
        )).add_header(header_parent_not_added)
    # when a valid header is added, the `add_header` call should succeed
    vmc.add_header(header1)
    mine(vmc, SHUFFLING_CYCLE_LENGTH)
    # if a header is added before, the second trial should fail
    with pytest.raises(BadFunctionCallOutput):
        vmc.call(vmc.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=default_gas,
            gas_price=1,
        )).add_header(header1)
    # when a valid header is added, the `add_header` call should succeed
    header2 = get_testing_colhdr(vmc, shard_id, header1_hash, 2)
    header2_hash = keccak(header2)
    vmc.add_header(header2)

    mine(vmc, SHUFFLING_CYCLE_LENGTH)
    # confirm the score of header1 and header2 are correct or not
    colhdr1_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header1_hash)
    assert colhdr1_score == 1
    colhdr2_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header2_hash)
    assert colhdr2_score == 2

    vmc.tx_to_shard(
        test_keys[1].public_key.to_canonical_address(),
        shard_id,
        100000,
        1,
        b'',
        value=1234567,
    )
    mine(vmc, 1)
    receipt_value = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_receipts__value(0)
    # the receipt value should be equaled to the transaction value
    assert receipt_value == 1234567

    # test `withdraw` ######################################
    do_withdraw(vmc, validator_index)
    mine(vmc, 1)
    # if the only validator withdraws, because there is no validator anymore, the result of sample
    # must be ZERO_ADDR.
    assert vmc.sample(shard_id) == ZERO_ADDR
