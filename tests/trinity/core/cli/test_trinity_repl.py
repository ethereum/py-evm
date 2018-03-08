import pytest

from trinity.console import console


def test_console(jsonrpc_ipc_pipe_path):
    # Test running the console, actually start it.
    with pytest.raises(OSError, match='^reading .* stdin .* captured$'):
        console(jsonrpc_ipc_pipe_path)


def test_python_console(jsonrpc_ipc_pipe_path):
    # Test running the default python REPL, actually start it.
    with pytest.raises(OSError, match='^reading .* stdin .* captured$'):
        console(jsonrpc_ipc_pipe_path, use_ipython=False)
