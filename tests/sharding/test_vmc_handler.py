import pytest

from eth_tester.exceptions import (
    TransactionFailed,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from evm.constants import (
    ZERO_ADDRESS,
)

from evm.rlp.headers import (
    CollationHeader,
)
from evm.utils.hexadecimal import (
    encode_hex,
)

from evm.vm.forks.sharding.log_handler import (
    LogHandler,
)
from evm.vm.forks.sharding.vmc_handler import (
    GENESIS_COLLATION_HASH,
    NextLogUnavailable,
    NoCandidateHead,
    ShardTracker,
    mk_build_transaction_detail,
    mk_contract_tx_detail,
    parse_collation_added_log,
)

from tests.sharding.fixtures import (  # noqa: F401
    add_header_constant_call,
    default_shard_id,
    default_validator_index,
    get_collation_score_call,
    mine,
    mk_colhdr_chain,
    mk_testing_colhdr,
    send_withdraw_tx,
    setup_shard_tracker,
    vmc,
    vmc_handler,
)


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


def test_mk_build_transaction_detail():  # noqa: F811
    # test `mk_build_transaction_detail` ######################################
    build_transaction_detail = mk_build_transaction_detail(
        nonce=0,
        gas=10000,
    )
    assert 'nonce' in build_transaction_detail
    assert 'gas' in build_transaction_detail
    assert 'chainId' in build_transaction_detail
    with pytest.raises(ValueError):
        build_transaction_detail = mk_build_transaction_detail(
            nonce=None,
            gas=10000,
        )
    with pytest.raises(ValueError):
        build_transaction_detail = mk_build_transaction_detail(
            nonce=0,
            gas=None,
        )


def test_mk_contract_tx_detail():  # noqa: F811
    # test `mk_contract_tx_detail` ######################################
    tx_detail = mk_contract_tx_detail(
        sender_address=ZERO_ADDRESS,
        gas=21000,
    )
    assert 'from' in tx_detail
    assert 'gas' in tx_detail
    with pytest.raises(ValueError):
        tx_detail = mk_contract_tx_detail(
            sender_address=ZERO_ADDRESS,
            gas=None,
        )
    with pytest.raises(ValueError):
        tx_detail = mk_contract_tx_detail(
            sender_address=None,
            gas=21000,
        )


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


# TODO: should separate the tests into pieces, and do some refactors
def test_vmc_contract_calls(vmc):  # noqa: F811
    setup_shard_tracker(vmc, default_shard_id)
    # test `add_header` ######################################
    # create a testing collation header, whose parent is the genesis
    header0_1 = mk_testing_colhdr(vmc, default_shard_id, GENESIS_COLLATION_HASH, 1)
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
    assert vmc.get_parent_hash(default_shard_id, header0_1.hash) == GENESIS_COLLATION_HASH
    assert vmc.get_parent_hash(default_shard_id, header0_2.hash) == header0_1.hash
    # confirm the logs are correct
    assert vmc.get_next_log(default_shard_id)['score'] == 2
    assert vmc.get_next_log(default_shard_id)['score'] == 1
    with pytest.raises(NextLogUnavailable):
        vmc.get_next_log(default_shard_id)

    # filter logs in multiple shards
    vmc.set_shard_tracker(1, ShardTracker(1, LogHandler(vmc.web3), vmc.address))
    header1_1 = mk_testing_colhdr(vmc, 1, GENESIS_COLLATION_HASH, 1)
    vmc.add_header(header1_1)
    mine(vmc, vmc.config['PERIOD_LENGTH'])
    header0_3 = mk_testing_colhdr(vmc, default_shard_id, header0_2.hash, 3)
    vmc.add_header(header0_3)
    mine(vmc, vmc.config['PERIOD_LENGTH'])
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
        get_default_account_keys()[1].public_key.to_canonical_address(),
        default_shard_id,
        100000,
        1,
        b'',
        value=1234567,
    )
    mine(vmc, 1)
    receipt_value = vmc.functions.get_receipts__value(0).call(
        vmc.mk_default_contract_tx_detail(),
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
