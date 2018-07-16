from logging import Logger
from multiprocessing import Process
import os
import pathlib
import signal
import time
from typing import Callable


def wait_for_ipc(ipc_path: pathlib.Path, timeout: int=1) -> None:
    start_at = time.time()
    while time.time() - start_at < timeout:
        if ipc_path.exists():
            break
        time.sleep(0.05)


def kill_process_gracefully(process: Process,
                            logger: Logger,
                            SIGINT_timeout: int=5,
                            SIGTERM_timeout: int=3) -> None:
    kill_process_id_gracefully(process.pid, process.join, logger, SIGINT_timeout, SIGTERM_timeout)


def kill_process_id_gracefully(
        process_id: int,
        wait_for_completion: Callable[[int], None],
        logger: Logger,
        SIGINT_timeout: int=5,
        SIGTERM_timeout: int=3) -> None:
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
