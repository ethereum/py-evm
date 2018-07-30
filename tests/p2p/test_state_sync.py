import os
import random
import time

from eth.db.backends.memory import MemoryDB
from eth.db.account import AccountDB
from eth.utils.logging import TraceLogger

from p2p.state import StateSync, TrieNodeRequestTracker


def make_random_state(n):
    raw_db = MemoryDB()
    account_db = AccountDB(raw_db)
    contents = {}
    for _ in range(n):
        addr = os.urandom(20)
        account_db.touch_account(addr)
        balance = random.randint(0, 10000)
        account_db.set_balance(addr, balance)
        nonce = random.randint(0, 10000)
        account_db.set_nonce(addr, nonce)
        storage = random.randint(0, 10000)
        account_db.set_storage(addr, 0, storage)
        code = b'not-real-code'
        account_db.set_code(addr, code)
        contents[addr] = (balance, nonce, storage, code)
    account_db.persist()
    return raw_db, account_db.state_root, contents


def test_state_sync():
    raw_db, state_root, contents = make_random_state(1000)
    dest_db = MemoryDB()
    scheduler = StateSync(state_root, dest_db)
    requests = scheduler.next_batch(10)
    while requests:
        results = []
        for request in requests:
            results.append([request.node_key, raw_db[request.node_key]])
        scheduler.process(results)
        requests = scheduler.next_batch(10)

    result_account_db = AccountDB(dest_db, state_root)
    for addr, account_data in contents.items():
        balance, nonce, storage, code = account_data
        assert result_account_db.get_balance(addr) == balance
        assert result_account_db.get_nonce(addr) == nonce
        assert result_account_db.get_storage(addr, 0) == storage
        assert result_account_db.get_code(addr) == code


REPLY_TIMEOUT = 5


def test_node_request_tracker_get_timed_out():
    tracker = TrieNodeRequestTracker(REPLY_TIMEOUT, TraceLogger('name'))
    peer1, peer2, peer3, peer4 = object(), object(), object(), object()
    peer_nodes = dict(
        (peer, [os.urandom(32) for _ in range(3)])
        for peer in [peer1, peer2, peer3, peer4])
    now = time.time()
    # Populate the tracker's active_requests with 4 requests, 2 of them made more than
    # REPLY_TIMEOUT seconds in the past and 2 made less than REPLY_TIMEOUT seconds ago.
    tracker.active_requests[peer1] = (now, peer_nodes[peer1])
    tracker.active_requests[peer2] = (now - REPLY_TIMEOUT - 1, peer_nodes[peer2])
    tracker.active_requests[peer3] = (now - REPLY_TIMEOUT - 2, peer_nodes[peer3])
    tracker.active_requests[peer4] = (now - REPLY_TIMEOUT + 1, peer_nodes[peer4])

    # get_timed_out() must return all node keys from requests made more than REPLY_TIMEOUT seconds
    # in the past.
    expected = set(peer_nodes[peer2] + peer_nodes[peer3])
    timed_out = tracker.get_timed_out()
    assert len(timed_out) == len(expected)
    assert set(timed_out) == expected

    # and it should remove the entries for those from the active_requests dict.
    assert peer2 not in tracker.active_requests
    assert peer3 not in tracker.active_requests
    assert peer1 in tracker.active_requests
    assert peer4 in tracker.active_requests


def test_node_request_tracker_get_retriable_missing():
    tracker = TrieNodeRequestTracker(REPLY_TIMEOUT, TraceLogger('name'))
    now = time.time()
    # Populate the tracker's missing dict with 4 requests, 2 of them made more than
    # REPLY_TIMEOUT seconds in the past and 2 made less than REPLY_TIMEOUT seconds ago.
    req1_time, req1_nodes = now, [os.urandom(32) for _ in range(3)]
    req2_time, req2_nodes = (now - REPLY_TIMEOUT - 1), [os.urandom(32) for _ in range(3)]
    req3_time, req3_nodes = (now - REPLY_TIMEOUT - 2), [os.urandom(32) for _ in range(3)]
    req4_time, req4_nodes = (now - REPLY_TIMEOUT + 1), [os.urandom(32) for _ in range(3)]
    tracker.missing[req1_time] = req1_nodes
    tracker.missing[req2_time] = req2_nodes
    tracker.missing[req3_time] = req3_nodes
    tracker.missing[req4_time] = req4_nodes

    expected = set(req2_nodes + req3_nodes)
    retriable_missing = tracker.get_retriable_missing()
    assert len(retriable_missing) == len(expected)
    assert set(retriable_missing) == expected

    assert req2_time not in tracker.missing
    assert req3_time not in tracker.missing
    assert req1_time in tracker.missing
    assert req4_time in tracker.missing


def test_node_request_tracker_get_next_timeout():
    tracker = TrieNodeRequestTracker(REPLY_TIMEOUT, TraceLogger('name'))
    oldest_req_time = 1234

    # Populate the tracker with missing and active requests, one of each made at oldest_req_time
    # and one of each made 1s after that.
    peer1, peer2 = object(), object()
    tracker.missing[oldest_req_time] = []
    tracker.missing[oldest_req_time + 1] = []
    tracker.active_requests[peer1] = (oldest_req_time, [])
    tracker.active_requests[peer2] = (oldest_req_time + 1, [])

    # Our next shcheduled timeout must be the oldest_req_time + REPLY_TIMEOUT
    assert tracker.get_next_timeout() == oldest_req_time + REPLY_TIMEOUT

    # Now, if we pop any of the requests made at oldest_req_time, but leave one behind, the next
    # scheduled timeout will still be the same since we still have one request made at
    # oldest_req_time.
    tracker.missing.pop(oldest_req_time)
    assert tracker.get_next_timeout() == oldest_req_time + REPLY_TIMEOUT

    # Removing the last remaining request made at oldest_req_time will cause the next scheduled
    # timeout to be (oldest_req_time + 1) + REPLY_TIMEOUT as expected.
    tracker.active_requests.pop(peer1)
    assert tracker.get_next_timeout() == oldest_req_time + 1 + REPLY_TIMEOUT
