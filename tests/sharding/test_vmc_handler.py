import logging

import pytest

import rlp

from eth_tester.exceptions import (
    TransactionFailed,
    ValidationError,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from eth_utils import (
    is_address,
    to_checksum_address,
)

from evm.utils.hexadecimal import (
    encode_hex,
)

from evm.vm.forks.byzantium.transactions import (
    ByzantiumTransaction,
)

from evm.rlp.headers import (
    CollationHeader,
)
from evm.vm.forks.sharding.log_handler import (
    LogHandler,
)
from evm.vm.forks.sharding.vmc_handler import (
    NextLogUnavailable,
    ShardTracker,
    parse_collation_added_data,
)
from evm.vm.forks.sharding.vmc_utils import (
    create_vmc_tx,
)

from tests.sharding.fixtures import (  # noqa: F401
    vmc,
)


PASSPHRASE = '123'
GENESIS_COLHDR_HASH = b'\x00' * 32
ZERO_ADDR = b'\x00' * 20

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


def is_vmc_deployed(vmc_handler):
    return (
        get_code(vmc_handler, vmc_handler.address) != b'' and
        get_nonce(vmc_handler, vmc_handler.vmc_tx_sender_address) != 0
    )


def mk_initiating_transactions(sender_privkey,
                               sender_starting_nonce,
                               TransactionClass,
                               gas_price):
    """Make VMC and its dependent transactions
    """
    nonce = sender_starting_nonce

    vmc_tx = create_vmc_tx(TransactionClass, gas_price=gas_price)

    # the sender gives all senders of the txs money, and append the
    # money-giving tx with the original tx to the return list

    funding_tx_for_tx_sender = TransactionClass.create_unsigned_transaction(
        nonce,
        gas_price,
        500000,
        vmc_tx.sender,
        vmc_tx.gas * vmc_tx.gas_price + vmc_tx.value,
        b'',
    ).as_signed_transaction(sender_privkey)
    nonce += 1
    return funding_tx_for_tx_sender, vmc_tx


def send_withdraw_tx(vmc_handler, validator_index):
    assert validator_index < len(test_keys)
    vmc_handler.withdraw(validator_index)
    mine(vmc_handler, 1)


def send_deposit_tx(vmc_handler):
    """
    Do deposit in VMC to be a validator

    :param privkey: PrivateKey object
    :return: returns the validator's address
    """
    mine(vmc_handler, 1)
    vmc_handler.deposit()
    return vmc_handler.get_default_sender_address()


def deploy_initiating_contracts(vmc_handler, privkey):
    w3 = vmc_handler.web3
    nonce = get_nonce(vmc_handler, privkey.public_key.to_canonical_address())
    txs = mk_initiating_transactions(
        privkey,
        nonce,
        ByzantiumTransaction,
        vmc_handler.config['GAS_PRICE'],
    )
    for tx in txs:
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


def mk_testing_colhdr(vmc_handler,
                      shard_id,
                      parent_hash,
                      number,
                      coinbase=test_keys[0].public_key.to_canonical_address()):
    period_length = vmc_handler.config['PERIOD_LENGTH']
    current_block_number = vmc_handler.web3.eth.blockNumber
    expected_period_number = (current_block_number + 1) // period_length
    logger.debug("mk_testing_colhdr: expected_period_number=%s", expected_period_number)

    period_start_prevblock_number = expected_period_number * period_length - 1
    period_start_prev_block = vmc_handler.web3.eth.getBlock(period_start_prevblock_number)
    period_start_prevhash = period_start_prev_block['hash']
    logger.debug("mk_testing_colhdr: period_start_prevhash=%s", period_start_prevhash)

    transaction_root = b"tx_list " * 4
    state_root = b"post_sta" * 4
    receipt_root = b"receipt " * 4

    collation_header = CollationHeader(
        shard_id=shard_id,
        expected_period_number=expected_period_number,
        period_start_prevhash=period_start_prevhash,
        parent_hash=parent_hash,
        transaction_root=transaction_root,
        coinbase=coinbase,
        state_root=state_root,
        receipt_root=receipt_root,
        number=number,
    )
    return collation_header


def add_header_constant_call(vmc_handler, collation_header):
    args = (
        getattr(collation_header, field[0])
        for field in collation_header.fields
    )
    # transform address from canonical to checksum_address, to comply with web3.py
    args_with_checksum_address = (
        to_checksum_address(item) if is_address(item) else item
        for item in args
    )
    # Here we use *args_with_checksum_address as the argument, to ensure the order of arguments
    # is the same as the one of parameters of `VMC.add_header`
    result = vmc_handler.call(vmc_handler.mk_contract_tx_detail(
        sender_address=vmc_handler.get_default_sender_address(),
        gas=vmc_handler.config['DEFAULT_GAS'],
        gas_price=1,
    )).add_header(*args_with_checksum_address)
    return result


@pytest.mark.parametrize(  # noqa: F811
    'mock_score,mock_is_new_head,expected_score,expected_is_new_head',
    (
        # test case in doc.md
        (
            (10, 11, 12, 11, 13, 14, 15, 11, 12, 13, 14, 12, 13, 14, 15, 16, 17, 18, 19, 16),
            (True, True, True, False, True, True, True, False, False, False, False, False, False, False, False, True, True, True, True, False),  # noqa: E501
            (19, 18, 17, 16, 16, 15, 15, 14, 14, 14, 13, 13, 13, 12, 12, 12, 11, 11, 11, 10),
            (True, True, True, True, False, True, False, True, False, False, True, False, False, True, False, False, True, False, False, True),  # noqa: E501
        ),
        (
            (1, 2, 3, 2, 2, 2),
            (True, True, True, False, False, False),
            (3, 2, 2, 2, 2, 1),
            (True, True, False, False, False, True),
        ),
    )
)
def test_shard_tracker_fetch_candidate_head(vmc,
                                            mock_score,
                                            mock_is_new_head,
                                            expected_score,
                                            expected_is_new_head):
    shard_id = 0
    log_handler = LogHandler(vmc.web3)
    shard_tracker = ShardTracker(shard_id, log_handler, vmc.address)
    mock_collation_added_logs = [
        {
            'header': [None] * 10,
            'score': mock_score[i],
            'is_new_head': mock_is_new_head[i],
        } for i in range(len(mock_score))
    ]
    # mock collation_added_logs
    shard_tracker.new_logs = mock_collation_added_logs
    for i in range(len(mock_score)):
        log = shard_tracker.fetch_candidate_head()
        assert log['score'] == expected_score[i]
        assert log['is_new_head'] == expected_is_new_head[i]
    with pytest.raises(NextLogUnavailable):
        log = shard_tracker.fetch_candidate_head()


def test_vmc_contract_calls(vmc):  # noqa: F811
    shard_id = 0
    validator_index = 0
    primary_key = test_keys[validator_index]
    primary_addr = primary_key.public_key.to_canonical_address()
    default_gas = vmc.config['DEFAULT_GAS']

    log_handler = LogHandler(vmc.web3)
    shard_tracker = ShardTracker(shard_id, log_handler, vmc.address)
    vmc.set_shard_tracker(shard_id, shard_tracker)
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
        gas=vmc.config['DEFAULT_GAS'],
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
            gas=vmc.config['DEFAULT_GAS'],
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

    lookahead_blocks = vmc.config['LOOKAHEAD_PERIODS'] * vmc.config['PERIOD_LENGTH']
    # test `deposit` and `get_eligible_proposer` ######################################
    # now we require 1 validator.
    # if there is currently no validator, we deposit one.
    # else, there should only be one validator, for easier testing.
    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_num_validators()
    if num_validators == 0:
        # deposit as the first validator
        validator_addr = send_deposit_tx(vmc)
        # TODO: error occurs when we don't mine so many blocks
        mine(vmc, lookahead_blocks)
        assert vmc.get_eligible_proposer(shard_id) == validator_addr

    # assert the current_block_number >= LOOKAHEAD_PERIODS * PERIOD_LENGTH
    # to ensure that `get_eligible_proposer` works
    current_block_number = vmc.web3.eth.blockNumber
    if current_block_number < lookahead_blocks:
        mine(vmc, lookahead_blocks - current_block_number)
    assert vmc.web3.eth.blockNumber >= lookahead_blocks

    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_num_validators()
    assert num_validators == 1
    assert vmc.get_eligible_proposer(shard_id) != ZERO_ADDR
    logger.debug("vmc_handler.get_num_validators()=%s", num_validators)

    # test `add_header` ######################################
    # create a testing collation header, whose parent is the genesis
    header0_1 = mk_testing_colhdr(vmc, shard_id, GENESIS_COLHDR_HASH, 1)
    # if a header is added before its parent header is added, `add_header` should fail
    # TransactionFailed raised when assertions fail
    with pytest.raises(TransactionFailed):
        header_parent_not_added = mk_testing_colhdr(
            vmc,
            shard_id,
            header0_1.hash,
            1,
        )
        add_header_constant_call(vmc, header_parent_not_added)
    # when a valid header is added, the `add_header` call should succeed
    vmc.add_header(header0_1)
    mine(vmc, vmc.config['PERIOD_LENGTH'])
    # if a header is added before, the second trial should fail
    with pytest.raises(TransactionFailed):
        add_header_constant_call(vmc, header0_1)
    # when a valid header is added, the `add_header` call should succeed
    header0_2 = mk_testing_colhdr(vmc, shard_id, header0_1.hash, 2)
    vmc.add_header(header0_2)

    mine(vmc, vmc.config['PERIOD_LENGTH'])
    # confirm the score of header1 and header2 are correct or not
    colhdr0_1_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header0_1.hash)
    assert colhdr0_1_score == 1
    colhdr0_2_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header0_2.hash)
    assert colhdr0_2_score == 2
    # confirm the logs are correct
    assert vmc.get_next_log(shard_id)['score'] == 2
    assert vmc.get_next_log(shard_id)['score'] == 1
    with pytest.raises(NextLogUnavailable):
        vmc.get_next_log(shard_id)

    # filter logs in multiple shards
    vmc.set_shard_tracker(1, ShardTracker(1, LogHandler(vmc.web3), vmc.address))
    header1_1 = mk_testing_colhdr(vmc, 1, GENESIS_COLHDR_HASH, 1)
    vmc.add_header(header1_1)
    mine(vmc, 1)
    header0_3 = mk_testing_colhdr(vmc, shard_id, header0_2.hash, 3)
    vmc.add_header(header0_3)
    mine(vmc, 1)
    assert vmc.get_next_log(0)['score'] == 3
    # ensure that `get_next_log(0)` does not affect `get_next_log(1)`
    assert vmc.get_next_log(1)['score'] == 1
    logs = vmc.web3.eth.getLogs({
        "fromBlock": 0,
        "toBlock": vmc.web3.eth.blockNumber,
        "topics": [
            encode_hex(ShardTracker.COLLATION_ADDED_TOPIC),
        ]
    })
    assert len(logs) == 4

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
    send_withdraw_tx(vmc, validator_index)
    mine(vmc, 1)
    # if the only validator withdraws, because there is no validator anymore, the result of
    # `get_num_validators` must be 0.
    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_num_validators()
    assert num_validators == 0


@pytest.mark.parametrize(
    'data_hex, expected_header_dict, expected_is_new_head, expected_score',
    (
        (
            '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000005db8d539409750d68b988e384ad6159d76f7a9f7985f8b290ea0875bf13d448c2000000000000000000000000000000000000000000000000000000000000000074785f6c6973742074785f6c6973742074785f6c6973742074785f6c697374200000000000000000000000007e5f4552091a69125d5dfcb7b8c2659029395bdf706f73745f737461706f73745f737461706f73745f737461706f73745f7374617265636569707420726563656970742072656365697074207265636569707420000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001',  # noqa: E501
            {'shard_id': 0, 'expected_period_number': 5, 'period_start_prevhash': b'\xdb\x8dS\x94\tu\rh\xb9\x88\xe3\x84\xadaY\xd7oz\x9fy\x85\xf8\xb2\x90\xea\x08u\xbf\x13\xd4H\xc2', 'parent_hash': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 'transaction_root': b'tx_list tx_list tx_list tx_list ', 'coinbase': b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', 'state_root': b'post_stapost_stapost_stapost_sta', 'receipt_root': b'receipt receipt receipt receipt ', 'number': 1},  # noqa: E501
            True,
            1,
        ),
        (
            '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000006d5e5e9350bb8ad57dd56e55e0b7aac054259b51c484e8d8ff64719e0a9d8d04698c7166041754720996f25b0988fb8192796a7f95879f397f6fc3a72dfa7023e74785f6c6973742074785f6c6973742074785f6c6973742074785f6c697374200000000000000000000000007e5f4552091a69125d5dfcb7b8c2659029395bdf706f73745f737461706f73745f737461706f73745f737461706f73745f7374617265636569707420726563656970742072656365697074207265636569707420000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000002',  # noqa: E501
            {'shard_id': 0, 'expected_period_number': 6, 'period_start_prevhash': b'\xd5\xe5\xe95\x0b\xb8\xadW\xddV\xe5^\x0bz\xac\x05BY\xb5\x1cHN\x8d\x8f\xf6G\x19\xe0\xa9\xd8\xd0F', 'parent_hash': b"\x98\xc7\x16`AuG \x99o%\xb0\x98\x8f\xb8\x19'\x96\xa7\xf9Xy\xf3\x97\xf6\xfc:r\xdf\xa7\x02>", 'transaction_root': b'tx_list tx_list tx_list tx_list ', 'coinbase': b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', 'state_root': b'post_stapost_stapost_stapost_sta', 'receipt_root': b'receipt receipt receipt receipt ', 'number': 2},  # noqa: E501
            True,
            2,
        ),
    )
)
def test_parse_collation_added_data(data_hex,
                                    expected_header_dict,
                                    expected_is_new_head,
                                    expected_score):
    parsed_data = parse_collation_added_data(data_hex)
    assert parsed_data['header'] == CollationHeader(**expected_header_dict)
    assert parsed_data['is_new_head'] == expected_is_new_head
    assert parsed_data['score'] == expected_score
