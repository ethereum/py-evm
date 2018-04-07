import pytest

from evm.rlp.headers import (
    CollationHeader,
)

from evm.vm.forks.sharding.shard_tracker import (
    parse_collation_added_log,
)

from tests.sharding.fixtures import (  # noqa: F401
    mine,
    make_collation_header_chain,
    shard_tracker,
    smc_handler,
)


@pytest.mark.parametrize(
    'log, expected_header_dict, expected_is_new_head, expected_height',
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
                                   expected_height):
    parsed_data = parse_collation_added_log(log)
    assert parsed_data['header'] == CollationHeader(**expected_header_dict)
    assert parsed_data['is_new_head'] == expected_is_new_head
    assert parsed_data['height'] == expected_height


def test_shard_tracker_new_logs(smc_handler):  # noqa: F811
    shard_tracker0 = shard_tracker(smc_handler, 0)
    make_collation_header_chain(smc_handler, 0, 2)
    # confirm the logs are correct
    new_logs_generator = shard_tracker0.new_logs()
    assert next(new_logs_generator)['height'] == 1
    assert next(new_logs_generator)['height'] == 2


@pytest.mark.parametrize(  # noqa: F811
    'mock_height,mock_period,expected_height,expected_period',
    (
        # test case in doc.md
        (
            (10, 11, 12, 11, 13, 14, 15, 11, 12, 13, 14, 12, 13, 14, 15, 16, 17, 18, 19, 16),
            (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19),
            (19, 18, 17, 16, 16, 15, 15, 14, 14, 14, 13, 13, 13, 12, 12, 12, 11, 11, 11, 10),
            (18, 17, 16, 15, 19, 6, 14, 5, 10, 13, 4, 9, 12, 2, 8, 11, 1, 3, 7, 0),
        ),
        (
            (1, 2, 3, 2, 2, 2),
            (0, 1, 2, 3, 4, 5),
            (3, 2, 2, 2, 2, 1),
            (2, 1, 3, 4, 5, 0),
        ),
    )
)
def test_fetch_candidate_heads_generator(smc_handler,
                                         mock_height,
                                         mock_period,
                                         expected_height,
                                         expected_period,
                                         monkeypatch):
    shard_tracker0 = shard_tracker(smc_handler, 0)

    mock_collation_added_logs = [
        {
            'header': CollationHeader(
                shard_id=0,
                expected_period_number=mock_period[i],
                period_start_prevhash=b'\x00' * 32,
                parent_hash=b'\x00' * 32,
                number=mock_height[i],
            ),
            'height': mock_height[i],
            'is_new_head': None,
        } for i in range(len(mock_height))
    ]

    def mock_shard_tracker_new_logs(self):
        for log in mock_collation_added_logs:
            yield log

    monkeypatch.setattr(
        'evm.vm.forks.sharding.shard_tracker.ShardTracker.new_logs',
        mock_shard_tracker_new_logs,
    )
    candidate_heads = shard_tracker0.fetch_candidate_heads_generator()
    for idx in range(len(expected_height)):
        candidate_header = next(candidate_heads)
        assert candidate_header.number == expected_height[idx]
        assert candidate_header.expected_period_number == expected_period[idx]

    with pytest.raises(StopIteration):
        next(candidate_heads)


def test_fetch_candidate_heads_generator_batches_logs(smc_handler, monkeypatch):  # noqa: F811
    shard_tracker0 = shard_tracker(smc_handler, 0)

    mock_height_batch1 = (10, 11, 12, 11, 13, 14, 15, 11, 12, 13)
    mock_period_batch1 = tuple(range(10))
    expected_height_after_batch1 = (15, 14, 13, 13, 12, 12, 11, 11, 11, 10)
    expected_period_after_batch1 = (6, 5, 4, 9, 2, 8, 1, 3, 7, 0)

    mock_height_batch2 = (14, 12, 13, 14, 15, 16, 17, 18, 19, 16)
    mock_period_batch2 = tuple(range(10, 20))
    expected_height_after_batch2 = (19, 18, 17, 16, 16, 15, 15, 14, 14, 14, 13, 13, 13, 12, 12, 12, 11, 11, 11, 10)  # noqa: E501
    expected_period_after_batch2 = (18, 17, 16, 15, 19, 6, 14, 5, 10, 13, 4, 9, 12, 2, 8, 11, 1, 3, 7, 0)  # noqa: E501

    mock_collation_added_logs = []

    mock_collation_added_logs.extend((
        {
            'header': CollationHeader(
                shard_id=0,
                expected_period_number=mock_period_batch1[i],
                period_start_prevhash=b'\x00' * 32,
                parent_hash=b'\x00' * 32,
                number=mock_height_batch1[i],
            ),
            'height': mock_height_batch1[i],
            'is_new_head': None,
        } for i in range(len(mock_height_batch1))
    ))

    def mock_shard_tracker_new_logs(self):
        for _ in range(len(mock_collation_added_logs)):
            yield mock_collation_added_logs.pop(0)

    monkeypatch.setattr(
        'evm.vm.forks.sharding.shard_tracker.ShardTracker.new_logs',
        mock_shard_tracker_new_logs,
    )
    candidate_heads = shard_tracker0.fetch_candidate_heads_generator()
    for idx in range(len(expected_height_after_batch1)):
        candidate_header = next(candidate_heads)
        assert candidate_header.number == expected_height_after_batch1[idx]
        assert candidate_header.expected_period_number == expected_period_after_batch1[idx]

    assert len(mock_collation_added_logs) == 0

    mock_collation_added_logs.extend((
        {
            'header': CollationHeader(
                shard_id=0,
                expected_period_number=mock_period_batch2[i],
                period_start_prevhash=b'\x00' * 32,
                parent_hash=b'\x00' * 32,
                number=mock_height_batch2[i],
            ),
            'height': mock_height_batch2[i],
            'is_new_head': None,
        } for i in range(len(mock_height_batch2))
    ))
    candidate_heads = shard_tracker0.fetch_candidate_heads_generator()
    for idx in range(len(expected_height_after_batch2)):
        candidate_header = next(candidate_heads)
        assert candidate_header.number == expected_height_after_batch2[idx]
        assert candidate_header.expected_period_number == expected_period_after_batch2[idx]
    with pytest.raises(StopIteration):
        next(candidate_heads)
