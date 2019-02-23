from logging import Logger
from multiprocessing import Process
import os
import pathlib
import signal
import subprocess
import time
from typing import Callable, Iterable


def wait_for_ipc(ipc_path: pathlib.Path, timeout: int=30) -> None:
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


def remove_dangling_ipc_files(logger: Logger,
                              ipc_dir: pathlib.Path,
                              except_file: pathlib.Path = None) -> None:

    if not ipc_dir.is_dir():
        raise Exception(f"The `ipc_dir` must be a directory but is {ipc_dir}")

    ipcfiles = tuple(ipc_dir.glob('*.ipc'))
    for ipcfile in ipcfiles:

        if ipcfile == except_file:
            continue

        try:
            ipcfile.unlink()
            logger.warning('Removed dangling IPC socket file  %s', ipcfile)
        except FileNotFoundError:
            logger.debug('ipcfile %s was already gone', ipcfile)


DEFAULT_SIGINT_TIMEOUT = 10
DEFAULT_SIGTERM_TIMEOUT = 5


def kill_process_gracefully(
        process: Process,
        logger: Logger,
        SIGINT_timeout: int=DEFAULT_SIGINT_TIMEOUT,
        SIGTERM_timeout: int=DEFAULT_SIGTERM_TIMEOUT) -> None:
    kill_process_id_gracefully(process.pid, process.join, logger, SIGINT_timeout, SIGTERM_timeout)


def kill_processes_gracefully(
        processes: Iterable[Process],
        logger: Logger,
        SIGINT_timeout: int=DEFAULT_SIGINT_TIMEOUT,
        SIGTERM_timeout: int=DEFAULT_SIGTERM_TIMEOUT) -> None:

    # Send SIGINT to each process without blocking
    for process in processes:
        sigint_process_id(process.pid, lambda _: None, logger, SIGINT_timeout)

    # Now block on each process as long as we have time left in the budget
    sigint_at = time.time()
    for process in processes:
        waited_sec = time.time() - sigint_at
        if waited_sec >= SIGINT_timeout:
            logger.debug("Waited %d on SIGINT, moving on", waited_sec)
            break
        process.join(SIGINT_timeout)

    # Send SIGTERM to each process without blocking
    for process in processes:
        sigterm_process_id(process.pid, lambda _: None, logger, SIGTERM_timeout)

    # Now block on each process as long as we have time left in the budget
    sigterm_at = time.time()
    for process in processes:
        waited_sec = time.time() - sigterm_at
        if waited_sec >= SIGTERM_timeout:
            logger.debug("Waited %d on SIGINT, moving on", waited_sec)
            break
        process.join(SIGTERM_timeout)

    for process in processes:
        sigkill_process_id(process.pid, logger)


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

    sigint_process_id(process_id, wait_for_completion, logger, SIGINT_timeout)
    sigterm_process_id(process_id, wait_for_completion, logger, SIGTERM_timeout)
    sigkill_process_id(process_id, logger)


def sigint_process_id(
        process_id: int,
        wait_for_completion: Callable[[int], None],
        logger: Logger,
        SIGINT_timeout: int=DEFAULT_SIGINT_TIMEOUT) -> None:

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


def sigterm_process_id(
        process_id: int,
        wait_for_completion: Callable[[int], None],
        logger: Logger,
        SIGTERM_timeout: int=DEFAULT_SIGTERM_TIMEOUT) -> None:

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


def sigkill_process_id(
        process_id: int,
        logger: Logger) -> None:

    try:
        os.kill(process_id, signal.SIGKILL)
    except ProcessLookupError:
        logger.info("Process %d has already terminated", process_id)
        return
    logger.info("Sent SIGKILL to process %d", process_id)
