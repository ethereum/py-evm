from pathlib import Path


def create_missing_ipc_error_message(ipc_path: Path) -> str:
    log_message = (
        "The IPC path at {0} is not found. \n"
        "Please run "
        "'trinity --data-dir <path-to-running-nodes-data-dir> attach' "
        "to specify the IPC path."
    ).format(str(ipc_path))
    return log_message
