import functools
import logging

from cytoolz import (
    compose,
)

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
    int_to_big_endian,
    is_canonical_address,
    pad_left,
    to_checksum_address,
)

from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.keccak import (
    keccak,
)

from evm.vm.forks.byzantium.transactions import (
    ByzantiumTransaction,
)

from evm.vm.forks.sharding.log_handler import (
    LogHandler,
)
from evm.vm.forks.sharding.vmc_utils import (
    create_vmc_tx,
)
from evm.vm.forks.sharding.vmc_handler import (
    NextLogUnavailable,
    ShardTracker,
    deserialize_header_bytes,
    parse_collation_added_data,
)

from tests.sharding.fixtures import (  # noqa: F401
    vmc,
)


PASSPHRASE = '123'
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
    """Make transactions of createing initial contracts
    Including rlp_decoder, sighasher and validator_manager
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


def do_withdraw(vmc_handler, validator_index):
    assert validator_index < len(test_keys)
    vmc_handler.withdraw(validator_index)
    mine(vmc_handler, 1)


def do_deposit(vmc_handler, privkey):
    """
    Deposit a validator

    :param privkey: PrivateKey object
    :return: returns the validator's address
    """
    address = privkey.public_key.to_canonical_address()
    mine(vmc_handler, 1)
    vmc_handler.deposit()
    return address


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
                      parent_collation_hash,
                      number,
                      collation_coinbase=test_keys[0].public_key.to_canonical_address()):
    period_length = vmc_handler.config['PERIOD_LENGTH']
    current_block_number = vmc_handler.web3.eth.blockNumber
    expected_period_number = (current_block_number + 1) // period_length
    logger.debug("mk_testing_colhdr: expected_period_number=%s", expected_period_number)

    period_start_prevblock_number = expected_period_number * period_length - 1
    period_start_prev_block = vmc_handler.web3.eth.getBlock(period_start_prevblock_number)
    period_start_prevhash = period_start_prev_block['hash']
    logger.debug("mk_testing_colhdr: period_start_prevhash=%s", period_start_prevhash)

    tx_list_root = b"tx_list " * 4
    post_state_root = b"post_sta" * 4
    receipt_root = b"receipt " * 4
    # temp function for casting int to bytes32
    pad_bytes_to_bytes32 = functools.partial(pad_left, to_size=32, pad_with=b'\x00')
    int_to_bytes32 = compose(
        pad_bytes_to_bytes32,
        int_to_big_endian,
    )
    header_hash = keccak(
        b''.join(
            (
                int_to_bytes32(shard_id),
                int_to_bytes32(expected_period_number),
                period_start_prevhash,
                parent_collation_hash,
                tx_list_root,
                pad_bytes_to_bytes32(collation_coinbase),
                post_state_root,
                receipt_root,
                int_to_bytes32(number),
            )
        )
    )
    header_tuple = (
        shard_id,
        expected_period_number,
        period_start_prevhash,
        parent_collation_hash,
        tx_list_root,
        collation_coinbase,
        post_state_root,
        receipt_root,
        number,
    )
    return header_tuple, header_hash


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
    primary_addr = test_keys[validator_index].public_key.to_canonical_address()
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
        validator_addr = do_deposit(vmc, primary_key)
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
    genesis_colhdr_hash = b'\x00' * 32
    # create a testing collation header, whose parent is the genesis
    header0_1, header0_1_hash = mk_testing_colhdr(vmc, shard_id, genesis_colhdr_hash, 1)
    # if a header is added before its parent header is added, `add_header` should fail
    # TransactionFailed raised when assertions fail
    with pytest.raises(TransactionFailed):
        header_parent_not_added, _ = mk_testing_colhdr(
            vmc,
            shard_id,
            header0_1_hash,
            1,
        )
        header_tuple_casting_address = (
            to_checksum_address(item)
            if is_canonical_address(item) else item
            for item in header_parent_not_added
        )
        vmc.call(vmc.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=default_gas,
            gas_price=1,
        )).add_header(*header_tuple_casting_address)
    # when a valid header is added, the `add_header` call should succeed
    vmc.add_header(*header0_1)
    mine(vmc, vmc.config['PERIOD_LENGTH'])
    # if a header is added before, the second trial should fail
    with pytest.raises(TransactionFailed):
        header0_1_casting_address = (
            to_checksum_address(item)
            if is_canonical_address(item) else item
            for item in header0_1
        )
        vmc.call(vmc.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=default_gas,
            gas_price=1,
        )).add_header(*header0_1_casting_address)
    # when a valid header is added, the `add_header` call should succeed
    header0_2, header0_2_hash = mk_testing_colhdr(vmc, shard_id, header0_1_hash, 2)
    vmc.add_header(*header0_2)

    mine(vmc, vmc.config['PERIOD_LENGTH'])
    # confirm the score of header1 and header2 are correct or not
    colhdr0_1_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header0_1_hash)
    assert colhdr0_1_score == 1
    colhdr0_2_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header0_2_hash)
    assert colhdr0_2_score == 2
    # confirm the logs are correct
    assert vmc.get_next_log(shard_id)['score'] == 2
    assert vmc.get_next_log(shard_id)['score'] == 1
    with pytest.raises(NextLogUnavailable):
        vmc.get_next_log(shard_id)

    # filter logs in multiple shards
    vmc.set_shard_tracker(1, ShardTracker(1, LogHandler(vmc.web3), vmc.address))
    header1_1, _ = mk_testing_colhdr(vmc, 1, genesis_colhdr_hash, 1)
    vmc.add_header(*header1_1)
    mine(vmc, 1)
    header0_3, _ = mk_testing_colhdr(vmc, shard_id, header0_2_hash, 3)
    vmc.add_header(*header0_3)
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
    do_withdraw(vmc, validator_index)
    mine(vmc, 1)
    # if the only validator withdraws, because there is no validator anymore, the result of
    # `get_num_validators` must be 0.
    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_num_validators()
    assert num_validators == 0


@pytest.mark.parametrize(
    'header_bytes, expected_header_tuple',
    (
        (
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x16\xa4\x96\xc9\r\x05\x05S\xee\xe2\xe2y\x95\x8fH\xa0\x8aT'j-\x94V\x1f\xa7|9r\xd7%\xdb\x1c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00tx_list tx_list tx_list tx_list \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdfpost_stapost_stapost_stapost_stareceipt receipt receipt receipt \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01",  # noqa: E501
            (0, 5, b"\x16\xa4\x96\xc9\r\x05\x05S\xee\xe2\xe2y\x95\x8fH\xa0\x8aT'j-\x94V\x1f\xa7|9r\xd7%\xdb\x1c", b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', b'tx_list tx_list tx_list tx_list ', b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', b'post_stapost_stapost_stapost_sta', b'receipt receipt receipt receipt ', 1),  # noqa: E501
        ),
        (
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x07\x11\x9b\x8f\xd4\xf2\xbbe /\xdf\'\xbcf~]\x9c\xf5\x08S\xe4\xbd\xa7\xee\xe2c\x83\x92\xdc-6>\xea\x8f8\x92\x998\x1aO}\x8c\xc0\xf0j\x90=O\xa2\x08o\rs\xa3d"a\x8d\xe3\x8dV\x80hC\xc0tx_list tx_list tx_list tx_list \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdfpost_stapost_stapost_stapost_stareceipt receipt receipt receipt \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03',  # noqa: E501
            (0, 7, b"\x11\x9b\x8f\xd4\xf2\xbbe /\xdf'\xbcf~]\x9c\xf5\x08S\xe4\xbd\xa7\xee\xe2c\x83\x92\xdc-6>\xea", b'\x8f8\x92\x998\x1aO}\x8c\xc0\xf0j\x90=O\xa2\x08o\rs\xa3d"a\x8d\xe3\x8dV\x80hC\xc0', b'tx_list tx_list tx_list tx_list ', b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', b'post_stapost_stapost_stapost_sta', b'receipt receipt receipt receipt ', 3),  # noqa: E501
        ),
    )
)
def test_deserialize_header_bytes(header_bytes, expected_header_tuple):
    actual_header_tuple = deserialize_header_bytes(header_bytes)
    assert actual_header_tuple == expected_header_tuple


@pytest.mark.parametrize(
    'data_hex, expected_header, expected_is_new_head, expected_score',
    (
        (
            '0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000587c46811ccae07f8e7b03c5f111764f6881bfe77dfbbbe9d3c0a86c054aee2b0000000000000000000000000000000000000000000000000000000000000000074785f6c6973742074785f6c6973742074785f6c6973742074785f6c697374200000000000000000000000007e5f4552091a69125d5dfcb7b8c2659029395bdf706f73745f737461706f73745f737461706f73745f737461706f73745f7374617265636569707420726563656970742072656365697074207265636569707420000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001',  # noqa: E501
            (0, 5, b'\x87\xc4h\x11\xcc\xae\x07\xf8\xe7\xb0<_\x11\x17d\xf6\x88\x1b\xfew\xdf\xbb\xbe\x9d<\n\x86\xc0T\xae\xe2\xb0', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', b'tx_list tx_list tx_list tx_list ', b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', b'post_stapost_stapost_stapost_sta', b'receipt receipt receipt receipt ', 1),  # noqa: E501
            True,
            1,
        ),
        (
            '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000006df996fe0bada20c6762c52239a5d8f4aed951903a649725737cbf88ea1009cc2835a26c9fee813d4301f6052c5970f4a01185f47a814bb6c5bfe98b26c77d3a474785f6c6973742074785f6c6973742074785f6c6973742074785f6c697374200000000000000000000000007e5f4552091a69125d5dfcb7b8c2659029395bdf706f73745f737461706f73745f737461706f73745f737461706f73745f7374617265636569707420726563656970742072656365697074207265636569707420000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000002',  # noqa: E501
            (0, 6, b'\xdf\x99o\xe0\xba\xda \xc6v,R#\x9a]\x8fJ\xed\x95\x19\x03\xa6IrW7\xcb\xf8\x8e\xa1\x00\x9c\xc2', b'\x83Z&\xc9\xfe\xe8\x13\xd40\x1f`R\xc5\x97\x0fJ\x01\x18_G\xa8\x14\xbbl[\xfe\x98\xb2lw\xd3\xa4', b'tx_list tx_list tx_list tx_list ', b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', b'post_stapost_stapost_stapost_sta', b'receipt receipt receipt receipt ', 2),  # noqa: E501
            True,
            2,
        ),
    )
)
def test_parse_collation_added_data(data_hex,
                                    expected_header,
                                    expected_is_new_head,
                                    expected_score):
    parsed_data = parse_collation_added_data(data_hex)
    assert parsed_data['header'] == expected_header
    assert parsed_data['is_new_head'] == expected_is_new_head
    assert parsed_data['score'] == expected_score
