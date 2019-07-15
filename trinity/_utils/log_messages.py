from pathlib import Path


def create_missing_ipc_error_message(ipc_path: Path) -> str:
    log_message = (
        f"The IPC path at {str(ipc_path)} is not found. \n"
        "Please run "
        "'trinity --data-dir <path-to-running-nodes-data-dir> attach' "
        "or 'trinity attach <path-to-jsonrpc.ipc>'"
        "to specify the IPC path."
    )
    return log_message
