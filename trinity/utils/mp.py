import multiprocessing
import os
import time


MP_CONTEXT = os.environ.get('TRINITY_MP_CONTEXT', 'spawn')


# sets the type of process that multiprocessing will create.
ctx = multiprocessing.get_context(MP_CONTEXT)


def wait_for_ipc(ipc_path, timeout=1):
    start_at = time.time()
    while time.time() - start_at < timeout:
        if os.path.exists(ipc_path):
            break
