import multiprocessing
import os
import signal
import time


MP_CONTEXT = os.environ.get('TRINITY_MP_CONTEXT', 'spawn')


# sets the type of process that multiprocessing will create.
ctx = multiprocessing.get_context(MP_CONTEXT)


def wait_for_ipc(ipc_path, timeout=1):
    start_at = time.time()
    while time.time() - start_at < timeout:
        if os.path.exists(ipc_path):
            break


def kill_processes_gracefully(*processes, logger=None, SIGINT_timeout=5, SIGTERM_timeout=3):
    try:
        for process in processes:
            if not process.is_alive():
                continue
            os.kill(process.pid, signal.SIGINT)
            process.join(SIGINT_timeout)
    except KeyboardInterrupt:
        if logger is not None:
            logger.info(
                "Waiting for processes to terminate.  You may force termination "
                "with CTRL+C two more times."
            )

    try:
        for process in processes:
            if not process.is_alive():
                continue
            os.kill(process.pid, signal.SIGTERM)
            process.join(SIGTERM_timeout)
    except KeyboardInterrupt:
        if logger is not None:
            logger.info(
                "Waiting for processes to terminate.  You may force termination "
                "with CTRL+C one more time."
            )

    for process in processes:
        if not process.is_alive():
            continue
        os.kill(process.pid, signal.SIGKILL)
