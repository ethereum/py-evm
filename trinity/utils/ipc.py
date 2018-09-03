from logging import Logger
from multiprocessing import Process
import os
import pathlib
import signal
import subprocess
import time
from typing import Callable


def wait_for_ipc(ipc_path: pathlib.Path, timeout: int=10) -> None:
    """
    Waits up to ``timeout`` seconds for the IPC socket file to appear at path
    ``ipc_path``, or raises a :exc:`TimeoutError` otherwise.
    """
    start_at = time.monotonic()
    while time.monotonic() - start_at < timeout:
        if ipc_path.exists():
            return
        else:
            time.sleep(0.05)
    # haven't `return`ed by now - raise unconditionally
    raise TimeoutError("IPC socket file has not appeared in %d seconds!" % timeout)


DEFAULT_SIGINT_TIMEOUT = 10
DEFAULT_SIGTERM_TIMEOUT = 5


def kill_process_gracefully(
        process: Process,
        logger: Logger,
        SIGINT_timeout: int=DEFAULT_SIGINT_TIMEOUT,
        SIGTERM_timeout: int=DEFAULT_SIGTERM_TIMEOUT) -> None:
    kill_process_id_gracefully(process.pid, process.join, logger, SIGINT_timeout, SIGTERM_timeout)


def kill_popen_gracefully(
        popen: subprocess.Popen,
        logger: Logger,
        SIGINT_timeout: int=DEFAULT_SIGINT_TIMEOUT,
        SIGTERM_timeout: int=DEFAULT_SIGTERM_TIMEOUT) -> None:

    def silent_timeout(timeout_len: int) -> None:
        try:
            popen.wait(timeout_len)
        except subprocess.TimeoutExpired:
            pass

    kill_process_id_gracefully(popen.pid, silent_timeout, logger, SIGINT_timeout, SIGTERM_timeout)


def kill_process_id_gracefully(
        process_id: int,
        wait_for_completion: Callable[[int], None],
        logger: Logger,
        SIGINT_timeout: int=DEFAULT_SIGINT_TIMEOUT,
        SIGTERM_timeout: int=DEFAULT_SIGTERM_TIMEOUT) -> None:
    try:
        try:
            os.kill(process_id, signal.SIGINT)
        except ProcessLookupError:
            logger.info("Process %d has already terminated", process_id)
            return
        logger.info(
            "Sent SIGINT to process %d, waiting %d seconds for it to terminate",
            process_id, SIGINT_timeout)
        wait_for_completion(SIGINT_timeout)
    except KeyboardInterrupt:
        logger.info(
            "Waiting for process to terminate.  You may force termination "
            "with CTRL+C two more times."
        )

    try:
        try:
            os.kill(process_id, signal.SIGTERM)
        except ProcessLookupError:
            logger.info("Process %d has already terminated", process_id)
            return
        logger.info(
            "Sent SIGTERM to process %d, waiting %d seconds for it to terminate",
            process_id, SIGTERM_timeout)
        wait_for_completion(SIGTERM_timeout)
    except KeyboardInterrupt:
        logger.info(
            "Waiting for process to terminate.  You may force termination "
            "with CTRL+C one more time."
        )

    try:
        os.kill(process_id, signal.SIGKILL)
    except ProcessLookupError:
        logger.info("Process %d has already terminated", process_id)
        return
    logger.info("Sent SIGKILL to process %d", process_id)
