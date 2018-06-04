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
                            logger: Logger,
                            SIGINT_timeout: int=5,
                            SIGTERM_timeout: int=3) -> None:
    try:
        if not process.is_alive():
            logger.info("Process %d has already terminated", process.pid)
            return
        os.kill(process.pid, signal.SIGINT)
        logger.info(
            "Sent SIGINT to process %d, waiting %d seconds for it to terminate",
            process.pid, SIGINT_timeout)
        process.join(SIGINT_timeout)
    except KeyboardInterrupt:
        logger.info(
            "Waiting for process to terminate.  You may force termination "
            "with CTRL+C two more times."
        )

    try:
        if not process.is_alive():
            return
        os.kill(process.pid, signal.SIGTERM)
        logger.info(
            "Sent SIGTERM to process %d, waiting %d seconds for it to terminate",
            process.pid, SIGTERM_timeout)
        process.join(SIGTERM_timeout)
    except KeyboardInterrupt:
        logger.info(
            "Waiting for process to terminate.  You may force termination "
            "with CTRL+C one more time."
        )

    if not process.is_alive():
        return
    os.kill(process.pid, signal.SIGKILL)
    logger.info("Sent SIGKILL to process %d", process.pid)
