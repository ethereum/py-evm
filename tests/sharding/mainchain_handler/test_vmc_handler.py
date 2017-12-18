import logging
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
    keccak,
    to_canonical_address,
    to_checksum_address,
)

from evm.utils.address import (
    generate_contract_address,
)
from evm.utils.hexadecimal import (
    encode_hex,
)

from evm.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
)

from evm.chains.sharding.mainchain_handler import (
    vmc_utils,
)

from evm.chains.sharding.mainchain_handler.config import (
    PERIOD_LENGTH,
    TX_GAS,
)

from evm.chains.sharding.mainchain_handler.vmc_handler import (
    VMC,
)

from evm.chains.sharding.mainchain_handler.vmc_utils import (
    create_vmc_tx,
    get_contract_address_from_contract_tx,
    get_vmc_json,
)

from tests.sharding.mainchain_handler.fixtures import (  # noqa: F401
    mainchain_handler,
)

PASSPHRASE = '123'
ZERO_ADDR = b'\x00' * 20
# for testing we set it to 5, 25 or 2500 originally
SHUFFLING_CYCLE_LENGTH = 5

test_keys = get_default_account_keys()

logger = logging.getLogger('evm.chain.sharding.mainchain_handler.VMCHandler')


def is_vmc_deployed(vmc_handler, chain_handler):
    return (
        # TODO: the following line should be uncommented when `get_code` is implemented in
        #       `eth_tester`
        # chain_handler.get_code(vmc_handler.address) != b'' and
        chain_handler.get_nonce(vmc_handler.sender_addr) != 0
    )


def do_withdraw(vmc_handler, chain_handler, validator_index):
    assert validator_index < len(test_keys)
    privkey = test_keys[validator_index]
    sender_addr = privkey.public_key.to_canonical_address()
    signature = vmc_utils.sign(vmc_utils.WITHDRAW_HASH, privkey)
    vmc_handler.withdraw(validator_index, signature, sender_addr)
    chain_handler.mine(1)


def deploy_valcode_and_deposit(vmc_handler, chain_handler, key):
    """
    Deploy validation code of and with the key, and do deposit

    :param key: Key object
    :return: returns nothing
    """
    address = key.public_key.to_canonical_address()
    chain_handler.unlock_account(address, PASSPHRASE)
    valcode = vmc_utils.mk_validation_code(
        key.public_key.to_canonical_address()
    )
    nonce = chain_handler.get_nonce(address)
    valcode_addr = generate_contract_address(to_canonical_address(address), nonce)
    chain_handler.unlock_account(address, PASSPHRASE)
    chain_handler.deploy_contract(valcode, address)
    chain_handler.mine(1)
    vmc_handler.deposit(valcode_addr, address, sender_addr=address)
    return valcode_addr


def deploy_initiating_contracts(vmc_handler, chain_handler, privkey):
    if not is_vmc_deployed(vmc_handler, chain_handler):
        address = privkey.public_key.to_canonical_address()
        chain_handler.unlock_account(address, PASSPHRASE)
        nonce = chain_handler.get_nonce(address)
        txs = vmc_utils.mk_initiating_contracts(privkey, nonce, SpuriousDragonTransaction)
        for tx in txs[:3]:
            chain_handler.direct_tx(tx)
        chain_handler.mine(1)
        for tx in txs[3:]:
            chain_handler.direct_tx(tx)
            chain_handler.mine(1)
        logger.debug(
            'deploy_initiating_contracts: vmc_tx_hash=%s',
            chain_handler.get_transaction_receipt(encode_hex(txs[-1].hash)),
        )


def import_key_to_mainchain_handler(chain_handler, key):
    """
    :param vmc_handler: VMCHandler
    :param privkey: PrivateKey object from eth_keys
    """
    try:
        chain_handler.w3.personal.importRawKey(key.to_hex(), PASSPHRASE)
    # Exceptions happen when the key is already imported.
    #   - ValueError: `web3.py`
    #   - ValidationError: `eth_tester`
    except (ValueError, ValidationError):
        pass


def get_testing_colhdr(vmc_handler,
                       chain_handler,
                       shard_id,
                       parent_collation_hash,
                       number,
                       collation_coinbase=test_keys[0].public_key.to_canonical_address(),
                       privkey=test_keys[0]):
    period_length = PERIOD_LENGTH
    expected_period_number = (chain_handler.get_block_number() + 1) // period_length
    logger.debug("get_testing_colhdr: expected_period_number=%s", expected_period_number)
    sender_addr = privkey.public_key.to_canonical_address()
    period_start_prevhash = vmc_handler.call(
        vmc_handler.mk_contract_tx_detail(sender_addr=sender_addr, gas=TX_GAS)
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

@pytest.fixture
def vmc(mainchain_handler):
    vmc_tx = create_vmc_tx(SpuriousDragonTransaction)
    vmc_addr = get_contract_address_from_contract_tx(vmc_tx)
    vmc_json = get_vmc_json()
    vmc_abi = vmc_json['abi']
    vmc_bytecode = vmc_json['bytecode']
    VMCClass = VMC.factory(mainchain_handler.w3, abi=vmc_abi, bytecode=vmc_bytecode)
    vmc = VMCClass(to_checksum_address(vmc_addr))
    vmc.sender_addr = vmc_tx.sender
    return vmc


def test_vmc_mk_contract_tx_detail(vmc):
    tx_detail = vmc.mk_contract_tx_detail(
        sender_addr=ZERO_ADDR,
        gas=TX_GAS,
    )
    assert 'from' in tx_detail
    assert 'gas' in tx_detail
    with pytest.raises(ValueError):
        tx_detail = vmc.mk_contract_tx_detail(
            sender_addr=ZERO_ADDR,
            gas=None,
        )
    with pytest.raises(ValueError):
        tx_detail = vmc.mk_contract_tx_detail(
            sender_addr=None,
            gas=TX_GAS,
        )


def test_vmc_contract_calls(vmc, mainchain_handler):  # noqa: F811
    shard_id = 0
    validator_index = 0
    primary_addr = test_keys[validator_index].public_key.to_canonical_address()
    default_gas = TX_GAS

    if not is_vmc_deployed(vmc, mainchain_handler):
        logger.debug('is_vmc_deployed(handler) == True')
        # import privkey
        for key in test_keys:
            import_key_to_mainchain_handler(mainchain_handler, key)

        deploy_initiating_contracts(vmc, mainchain_handler, test_keys[validator_index])
        mainchain_handler.mine(1)
        valcode_addr = deploy_valcode_and_deposit(vmc, mainchain_handler, test_keys[validator_index])
        # TODO: error occurs when we don't mine so many blocks
        mainchain_handler.mine(SHUFFLING_CYCLE_LENGTH)
        assert vmc.sample(shard_id, primary_addr) == valcode_addr

    assert is_vmc_deployed(vmc, mainchain_handler)

    mainchain_handler.mine(SHUFFLING_CYCLE_LENGTH)

    assert vmc.sample(shard_id, primary_addr) != ZERO_ADDR
    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_addr=primary_addr, gas=default_gas)
    ).get_num_validators()
    assert num_validators > 0
    logger.debug("vmc_handler.get_num_validators()=%s", num_validators)

    genesis_colhdr_hash = b'\x00' * 32
    header1 = get_testing_colhdr(vmc, mainchain_handler, shard_id, genesis_colhdr_hash, 1)
    header1_hash = keccak(header1)
    # BadFunctionCallOutput raised when assertions fail
    with pytest.raises(BadFunctionCallOutput):
        header_parent_not_added = get_testing_colhdr(
            vmc,
            mainchain_handler,
            shard_id,
            header1_hash,
            1,
        )
        vmc.call(vmc.mk_contract_tx_detail(
            sender_addr=primary_addr,
            gas=default_gas,
            gas_price=1,
        )).add_header(header_parent_not_added)
    vmc.add_header(header1, primary_addr)
    mainchain_handler.mine(SHUFFLING_CYCLE_LENGTH)
    # not be able to add the same header again
    with pytest.raises(BadFunctionCallOutput):
        vmc.call(vmc.mk_contract_tx_detail(
            sender_addr=primary_addr,
            gas=default_gas,
            gas_price=1,
        )).add_header(header1)

    header2 = get_testing_colhdr(vmc, mainchain_handler, shard_id, header1_hash, 2)
    header2_hash = keccak(header2)
    vmc.add_header(header2, primary_addr)
    mainchain_handler.mine(SHUFFLING_CYCLE_LENGTH)

    colhdr1_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_addr=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header1_hash)
    assert colhdr1_score == 1
    colhdr2_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_addr=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header2_hash)
    assert colhdr2_score == 2

    vmc.tx_to_shard(
        test_keys[1].public_key.to_canonical_address(),
        shard_id,
        100000,
        1,
        b'',
        1234567,
        primary_addr,
    )
    mainchain_handler.mine(1)
    receipt_value = vmc.call(
        vmc.mk_contract_tx_detail(sender_addr=primary_addr, gas=default_gas)
    ).get_receipts__value(0)
    assert receipt_value == 1234567

    do_withdraw(vmc, mainchain_handler, validator_index)
    mainchain_handler.mine(1)
    assert vmc.sample(shard_id, primary_addr) == ZERO_ADDR
