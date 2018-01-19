import os
import logging
import random

from evm.db.backends.memory import MemoryDB
from evm.db.state import AccountStateDB
from evm.p2p.state import StateSync


def make_random_state(n):
    state_db = AccountStateDB(MemoryDB())
    contents = {}
    for i in range(n):
        addr = os.urandom(20)
        state_db.touch_account(addr)
        balance = random.randint(0, 10000)
        state_db.set_balance(addr, balance)
        nonce = random.randint(0, 10000)
        state_db.set_nonce(addr, nonce)
        storage = random.randint(0, 10000)
        state_db.set_storage(addr, 0, storage)
        code = b'not-real-code'
        state_db.set_code(addr, code)
        contents[addr] = (balance, nonce, storage, code)
    return state_db, contents


def test_state_sync():
    state_db, contents = make_random_state(1000)
    dest_db = {}
    scheduler = StateSync(state_db.root_hash, dest_db, logging.getLogger())
    requests = scheduler.next_batch(10)
    while len(requests) > 0:
        results = []
        for request in requests:
            results.append([request.node_key, state_db.db[request.node_key]])
        scheduler.process(results)
        requests = scheduler.next_batch(10)
    dest_state = AccountStateDB(dest_db, state_db.root_hash)
    for addr, account_data in contents.items():
        balance, nonce, storage, code = account_data
        assert dest_state.get_balance(addr) == balance
        assert dest_state.get_nonce(addr) == nonce
        assert dest_state.get_storage(addr, 0) == storage
        assert dest_state.get_code(addr) == code
