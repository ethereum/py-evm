import asyncio
import json
import os

from cytoolz import curry
from eth_utils import decode_hex

from evm import MainnetTesterChain
from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.rpc.main import RPCServer


@curry
async def connection_handler(execute_rpc, reader, writer):
    raw_request = ''
    while True:
        request_bytes = b''
        try:
            request_bytes = await reader.readuntil(b'}')
        except asyncio.IncompleteReadError as e:
            print(
                "What's really going to bake your noodle later on is,",
                "would you still have broken it if I hadn't said anything?",
                "Incomplete Read Error",
                e,
            )
            break
        except asyncio.LimitOverrunError:
            continue
        except Exception as e:
            print(
                "There's a difference between knowing the path, and walking the path.",
                "Unknown read issue: ",
                e,
            )

        raw_request += request_bytes.decode()

        try:
            request = json.loads(raw_request)
        except json.JSONDecodeError:
            # invalid json request, keep reading data until a valid json is formed
            continue

        if request:
            result = execute_rpc(request)
            writer.write(result.encode())
        else:
            break

        try:
            raw_request = ''
            await writer.drain()
        except ConnectionResetError:
            break


def start(path, chain):
    loop = asyncio.get_event_loop()
    rpc = RPCServer(chain)
    loop.run_until_complete(asyncio.start_unix_server(
        connection_handler(rpc.execute),
        path,
        loop=loop,
    ))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print('Tank, I need an exit!')
    finally:
        loop.close()


def get_test_chain():
    root_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..')
    db_path = os.path.join(root_path, 'tests', 'fixtures', 'rpc_test_chain.db')
    db = MemoryDB()
    with open(db_path) as f:
        key_val_hex = json.loads(f.read())
        db.kv_store = {decode_hex(k): decode_hex(v) for k, v in key_val_hex.items()}
    chain_db = BaseChainDB(db)
    return MainnetTesterChain(chain_db)


if __name__ == '__main__':
    start('/tmp/test.ipc', get_test_chain())
