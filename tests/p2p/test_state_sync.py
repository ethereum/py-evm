import os
import random

from eth.db.backends.memory import MemoryDB
from eth.db.account import AccountDB

from p2p.state import StateSync


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
