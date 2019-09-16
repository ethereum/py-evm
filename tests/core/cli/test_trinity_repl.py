import pytest

from trinity.components.builtin.attach.console import console
from pathlib import Path
from trinity._utils.log_messages import (
    create_missing_ipc_error_message,
)


def test_console(caplog, jsonrpc_ipc_pipe_path):
    # if ipc_path is not found, raise an exception with a useful message
    with pytest.raises(FileNotFoundError):
        console(Path(jsonrpc_ipc_pipe_path))
        assert create_missing_ipc_error_message(jsonrpc_ipc_pipe_path) in caplog.text


def test_python_console(caplog, jsonrpc_ipc_pipe_path):
    # if ipc_path is not found, raise an exception with a useful message
    with pytest.raises(FileNotFoundError):
        console(Path(jsonrpc_ipc_pipe_path), use_ipython=False)
        assert create_missing_ipc_error_message(jsonrpc_ipc_pipe_path) in caplog.text
