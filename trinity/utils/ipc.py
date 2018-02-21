import os
import signal
import time


def wait_for_ipc(ipc_path, timeout=1):
    start_at = time.time()
    while time.time() - start_at < timeout:
        if os.path.exists(ipc_path):
            break
        time.sleep(0.05)


def kill_process_gracefully(process, logger=None, SIGINT_timeout=5, SIGTERM_timeout=3):
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
