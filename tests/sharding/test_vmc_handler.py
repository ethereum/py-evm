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

from evm.constants import (
    ZERO_ADDRESS,
    ZERO_HASH32,
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
    NoCandidateHead,
    ShardTracker,
    fetch_and_verify_collation,
    parse_collation_added_log,
)
from evm.vm.forks.sharding.vmc_utils import (
    create_vmc_tx,
)

from tests.sharding.fixtures import (  # noqa: F401
    vmc,
)


PASSPHRASE = '123'
GENESIS_COLHDR_HASH = b'\x00' * 32

test_keys = get_default_account_keys()
default_shard_id = 0
default_validator_index = 0
primary_key = test_keys[default_validator_index]
primary_addr = primary_key.public_key.to_canonical_address()

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


def setup_shard_tracker(vmc_handler, shard_id):
    log_handler = LogHandler(vmc_handler.web3)
    shard_tracker = ShardTracker(shard_id, log_handler, vmc_handler.address)
    vmc_handler.set_shard_tracker(shard_id, shard_tracker)


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
        tx_hash = send_raw_transaction(vmc_handler, tx)
        mine(vmc_handler, 1)
        assert w3.eth.getTransactionReceipt(tx_hash) is not None
    logger.debug(
        'deploy_initiating_contracts: vmc_tx_hash=%s',
        w3.eth.getTransactionReceipt(encode_hex(txs[-1].hash)),
    )


def deploy_vmc(vmc_handler):
    # test the deployment of vmc ######################################
    # deploy vmc if it is not deployed yet.
    if not is_vmc_deployed(vmc_handler):
        logger.debug('is_vmc_deployed(vmc) == False')
        # import test_key
        import_key(vmc_handler, primary_key)
        deploy_initiating_contracts(vmc_handler, primary_key)
        mine(vmc_handler, 1)

    assert is_vmc_deployed(vmc_handler)


def add_validator(vmc_handler):
    assert is_vmc_deployed(vmc_handler)

    lookahead_blocks = vmc_handler.config['LOOKAHEAD_PERIODS'] * vmc_handler.config['PERIOD_LENGTH']
    # test `deposit` and `get_eligible_proposer` ######################################
    # now we require 1 validator.
    # if there is currently no validator, we deposit one.
    # else, there should only be one validator, for easier testing.
    num_validators = vmc_handler.functions.get_num_validators().call(
        vmc_handler.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=vmc_handler.config['DEFAULT_GAS'],
        )
    )

    validator_addr = send_deposit_tx(vmc_handler)
    # TODO: error occurs when we don't mine so many blocks
    mine(vmc_handler, lookahead_blocks)
    assert vmc_handler.get_eligible_proposer(default_shard_id) == validator_addr

    # assert the current_block_number >= LOOKAHEAD_PERIODS * PERIOD_LENGTH
    # to ensure that `get_eligible_proposer` works
    current_block_number = vmc_handler.web3.eth.blockNumber
    if current_block_number < lookahead_blocks:
        mine(vmc_handler, lookahead_blocks - current_block_number)
    assert vmc_handler.web3.eth.blockNumber >= lookahead_blocks

    current_num_validators = vmc_handler.functions.get_num_validators().call(
        vmc_handler.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=vmc_handler.config['DEFAULT_GAS'],
        )
    )
    assert current_num_validators == num_validators + 1
    assert vmc_handler.get_eligible_proposer(default_shard_id) != ZERO_ADDRESS
    logger.debug("vmc_handler.get_num_validators()=%s", num_validators)


def deploy_vmc_and_add_one_validator(vmc_handler):
    deploy_vmc(vmc_handler)
    num_validators = vmc_handler.functions.get_num_validators().call(
        vmc_handler.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=vmc_handler.config['DEFAULT_GAS'],
        )
    )
    if num_validators == 0:
        add_validator(vmc_handler)


def send_deposit_tx(vmc_handler):
    """
    Do deposit in VMC to be a validator

    :param privkey: PrivateKey object
    :return: returns the validator's address
    """
    vmc_handler.deposit()
    mine(vmc_handler, vmc_handler.config['PERIOD_LENGTH'])
    return vmc_handler.get_default_sender_address()


def send_withdraw_tx(vmc_handler, validator_index):
    assert validator_index < len(test_keys)
    vmc_handler.withdraw(validator_index)
    mine(vmc_handler, 1)


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
    result = vmc_handler.functions.add_header(
        *args_with_checksum_address
    ).call(
        vmc_handler.mk_contract_tx_detail(
            sender_address=vmc_handler.get_default_sender_address(),
            gas=vmc_handler.config['DEFAULT_GAS'],
            gas_price=1,
        )
    )
    return result


def get_collation_score_call(vmc_handler, shard_id, collation_hash):
    collation_score = vmc_handler.functions.get_collation_headers__score(
        default_shard_id,
        collation_hash,
    ).call(
        vmc_handler.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=vmc_handler.config["DEFAULT_GAS"],
        )
    )
    return collation_score


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


def mk_colhdr_chain(vmc_handler, shard_id, num_collations, top_collation_hash=GENESIS_COLHDR_HASH):
    """
    Make a collation header chain from genesis collation
    :return: the collation hash of the tip of the chain
    """
    for _ in range(num_collations):
        top_collation_number = get_collation_score_call(vmc_handler, shard_id, top_collation_hash)
        header = mk_testing_colhdr(
            vmc_handler,
            shard_id,
            top_collation_hash,
            top_collation_number + 1,
        )
        assert add_header_constant_call(vmc_handler, header)
        tx_hash = vmc_handler.add_header(header)
        mine(vmc_handler, vmc_handler.config['PERIOD_LENGTH'])
        assert vmc_handler.web3.eth.getTransactionReceipt(tx_hash) is not None
        top_collation_hash = header.hash
    return top_collation_hash


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
    with pytest.raises(NoCandidateHead):
        log = shard_tracker.fetch_candidate_head()


def test_vmc_mk_build_transaction_detail(vmc):  # noqa: F811
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


def test_vmc_mk_contract_tx_detail(vmc):  # noqa: F811
    # test `mk_contract_tx_detail` ######################################
    tx_detail = vmc.mk_contract_tx_detail(
        sender_address=ZERO_ADDRESS,
        gas=vmc.config['DEFAULT_GAS'],
    )
    assert 'from' in tx_detail
    assert 'gas' in tx_detail
    with pytest.raises(ValueError):
        tx_detail = vmc.mk_contract_tx_detail(
            sender_address=ZERO_ADDRESS,
            gas=None,
        )
    with pytest.raises(ValueError):
        tx_detail = vmc.mk_contract_tx_detail(
            sender_address=None,
            gas=vmc.config['DEFAULT_GAS'],
        )


# TODO: add tests for memoized_fetch_and_verify_collation respectively
def test_vmc_guess_head(vmc):  # noqa: F811
    deploy_vmc_and_add_one_validator(vmc)
    setup_shard_tracker(vmc, default_shard_id)

    # without fork
    header0_2_hash = mk_colhdr_chain(vmc, default_shard_id, 2)
    assert vmc.guess_head(default_shard_id) == header0_2_hash

    # with fork
    header0_3_prime_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    # head changes
    assert vmc.guess_head(default_shard_id) == header0_3_prime_hash


def test_guess_head_invalid_first_candidate(monkeypatch, vmc):  # noqa: F811
    deploy_vmc_and_add_one_validator(vmc)
    setup_shard_tracker(vmc, default_shard_id)

    # setup two collation header chains, both having length=3.
    # originally, guess_head should return the hash of canonical chain head `header0_3_hash`
    header3_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    header3_prime_hash = mk_colhdr_chain(vmc, default_shard_id, 3)

    def mock_fetch_and_verify_collation(collation_hash):
        if collation_hash == header3_hash:
            return False
        return True
    # mock `fetch_and_verify_collation`, make it consider collation `header0_3_hash` is invalid
    fetch_and_verify_collation_import_path = "{0}.{1}".format(
        fetch_and_verify_collation.__module__,
        fetch_and_verify_collation.__name__,
    )
    monkeypatch.setattr(
        fetch_and_verify_collation_import_path,
        mock_fetch_and_verify_collation,
    )
    # the candidates is  [`header3`, `header3_prime`, `header2`, ...]
    # since the 1st candidate is invalid, `guess_head` should returns `header3_prime` instead
    assert vmc.guess_head(default_shard_id) == header3_prime_hash


# TODO: should separate the tests into pieces, and do some refactors
def test_vmc_contract_calls(vmc):  # noqa: F811
    default_gas = vmc.config['DEFAULT_GAS']

    deploy_vmc_and_add_one_validator(vmc)
    setup_shard_tracker(vmc, default_shard_id)

    # test `add_header` ######################################
    # create a testing collation header, whose parent is the genesis
    header0_1 = mk_testing_colhdr(vmc, default_shard_id, GENESIS_COLHDR_HASH, 1)
    # if a header is added before its parent header is added, `add_header` should fail
    # TransactionFailed raised when assertions fail
    with pytest.raises(TransactionFailed):
        header_parent_not_added = mk_testing_colhdr(
            vmc,
            default_shard_id,
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
    header0_2 = mk_testing_colhdr(vmc, default_shard_id, header0_1.hash, 2)
    vmc.add_header(header0_2)

    mine(vmc, vmc.config['PERIOD_LENGTH'])
    # confirm the score of header1 and header2 are correct or not
    colhdr0_1_score = vmc.functions.get_collation_headers_score(
        shard_id,
        header0_1.hash,
    ).call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    )
    assert colhdr0_1_score == 1
    colhdr0_2_score = vmc.functions.get_collation_headers_score(
        shard_id,
        header0_2.hash,
    ).call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    )
    assert colhdr0_2_score == 2
    # assert parent_hashes
    assert vmc.get_parent_hash(default_shard_id, header0_1.hash) == ZERO_HASH32
    assert vmc.get_parent_hash(default_shard_id, header0_2.hash) == header0_1.hash
    # confirm the logs are correct
    assert vmc.get_next_log(default_shard_id)['score'] == 2
    assert vmc.get_next_log(default_shard_id)['score'] == 1
    with pytest.raises(NextLogUnavailable):
        vmc.get_next_log(default_shard_id)

    # filter logs in multiple shards
    vmc.set_shard_tracker(1, ShardTracker(1, LogHandler(vmc.web3), vmc.address))
    header1_1 = mk_testing_colhdr(vmc, 1, GENESIS_COLHDR_HASH, 1)
    vmc.add_header(header1_1)
    mine(vmc, 1)
    header0_3 = mk_testing_colhdr(vmc, default_shard_id, header0_2.hash, 3)
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

    # test `tx_to_shard` ######################################
    vmc.tx_to_shard(
        test_keys[1].public_key.to_canonical_address(),
        default_shard_id,
        100000,
        1,
        b'',
        value=1234567,
    )
    mine(vmc, 1)
    receipt_value = vmc.functions.get_receipts__value(0).call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    )
    # the receipt value should be equaled to the transaction value
    assert receipt_value == 1234567

    # test `withdraw` ######################################
    send_withdraw_tx(vmc, default_validator_index)
    mine(vmc, 1)
    # if the only validator withdraws, because there is no validator anymore, the result of
    # `get_num_validators` must be 0.
    num_validators = vmc.functions.num_validators().call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    )
    assert num_validators == 0


@pytest.mark.parametrize(
    'log, expected_header_dict, expected_is_new_head, expected_score',
    (
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x000000000000000000000000000000000000000000000000000000000000000534c998a5b8325a1276f385558aae7f5c3f8a40023d289f39649d2fcdd7d49100000000000000000000000000000000000000000000000000000000000000000074785f6c6973742074785f6c6973742074785f6c6973742074785f6c697374200000000000000000000000007e5f4552091a69125d5dfcb7b8c2659029395bdf706f73745f737461706f73745f737461706f73745f737461706f73745f7374617265636569707420726563656970742072656365697074207265636569707420000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001', 'topics': [b'\x95\x86g\xed\xf5J\xea\x9d\xfa[\xee!\xb2\xb4\x9f|\x11D\xe4[\xa0h"\xa3\xa5\x8fc\x90\xa9\xa1\xc5C', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00']},  # noqa: E501
            {'shard_id': 0, 'expected_period_number': 5, 'period_start_prevhash': b'4\xc9\x98\xa5\xb82Z\x12v\xf3\x85U\x8a\xae\x7f\\?\x8a@\x02=(\x9f9d\x9d/\xcd\xd7\xd4\x91\x00', 'parent_hash': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 'transaction_root': b'tx_list tx_list tx_list tx_list ', 'coinbase': b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', 'state_root': b'post_stapost_stapost_stapost_sta', 'receipt_root': b'receipt receipt receipt receipt ', 'number': 1},  # noqa: E501
            True,
            1,
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\x16\xc2\x0b\xadZ|\x92l@@\xb1\x15\x93nh\xd6]p\x16\xae\xd5\xe7\x9crKl\x8c\xcf\x06\x9a\xd4\x05', 'blockHash': b'\x94\\\xce\x19\x01:j\xbb\xf8\xba\x19\xcfv\xc3z3}^\xb6>\xa0\x0e\xf74\xe8A\t\x12p\x9a\xf6V', 'blockNumber': 30, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000006833a3857300f5dc95cb88d3473ea3158c7d386ac0537d614662f9de55c610c230e5f6e7e4d527c69ee38d61018b7fd8cc5d563abddcfaaaf704a43fd870cf6bf74785f6c6973742074785f6c6973742074785f6c6973742074785f6c697374200000000000000000000000007e5f4552091a69125d5dfcb7b8c2659029395bdf706f73745f737461706f73745f737461706f73745f737461706f73745f7374617265636569707420726563656970742072656365697074207265636569707420000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000002', 'topics': [b'\x95\x86g\xed\xf5J\xea\x9d\xfa[\xee!\xb2\xb4\x9f|\x11D\xe4[\xa0h"\xa3\xa5\x8fc\x90\xa9\xa1\xc5C', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00']},  # noqa: E501
            {'shard_id': 0, 'expected_period_number': 6, 'period_start_prevhash': b'\x83:8W0\x0f]\xc9\\\xb8\x8d4s\xea1X\xc7\xd3\x86\xac\x057\xd6\x14f/\x9d\xe5\\a\x0c#', 'parent_hash': b'\x0e_n~MR|i\xee8\xd6\x10\x18\xb7\xfd\x8c\xc5\xd5c\xab\xdd\xcf\xaa\xafpJC\xfd\x87\x0c\xf6\xbf', 'transaction_root': b'tx_list tx_list tx_list tx_list ', 'coinbase': b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', 'state_root': b'post_stapost_stapost_stapost_sta', 'receipt_root': b'receipt receipt receipt receipt ', 'number': 2},  # noqa: E501
            True,
            2,
        ),
    )
)
def test_parse_collation_added_log(log,
                                   expected_header_dict,
                                   expected_is_new_head,
                                   expected_score):
    parsed_data = parse_collation_added_log(log)
    assert parsed_data['header'] == CollationHeader(**expected_header_dict)
    assert parsed_data['is_new_head'] == expected_is_new_head
    assert parsed_data['score'] == expected_score
