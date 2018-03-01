import os
import signal
import time
from multiprocessing import Process
from logging import Logger


def wait_for_ipc(ipc_path: str, timeout: int=1) -> None:
    start_at = time.time()
    while time.time() - start_at < timeout:
        if os.path.exists(ipc_path):
            break
        time.sleep(0.05)


def kill_process_gracefully(process: Process,
                            logger: Logger=None,
                            SIGINT_timeout: int=5,
                            SIGTERM_timeout: int=3) -> None:
    try:
        if not process.is_alive():
            return
        os.kill(process.pid, signal.SIGINT)
        process.join(SIGINT_timeout)
    except KeyboardInterrupt:
        if logger is not None:
            logger.info(
                "Waiting for processes to terminate.  You may force termination "
                "with CTRL+C two more times."
            )

    try:
        if not process.is_alive():
            return
        os.kill(process.pid, signal.SIGTERM)
        process.join(SIGTERM_timeout)
    except KeyboardInterrupt:
        if logger is not None:
            logger.info(
                "Waiting for processes to terminate.  You may force termination "
                "with CTRL+C one more time."
            )

    if not process.is_alive():
        return
    os.kill(process.pid, signal.SIGKILL)
