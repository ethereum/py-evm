from abc import ABC, abstractmethod
import contextlib
import errno
import logging
import pathlib
import socket
import threading
from typing import Iterator


class BufferedSocket:
    def __init__(self, sock: socket.socket) -> None:
        self._socket = sock
        self._buffer = bytearray()
        self.sendall = sock.sendall
        self.close = sock.close
        self.shutdown = sock.shutdown

    def read_exactly(self, num_bytes: int) -> bytes:
        while len(self._buffer) < num_bytes:

            data = self._socket.recv(4096)

            if data == b"":
                raise OSError("Connection closed")

            self._buffer.extend(data)
        payload = self._buffer[:num_bytes]
        self._buffer = self._buffer[num_bytes:]
        return bytes(payload)


class IPCSocketServer(ABC):
    """
    Implements an interface for serving the BaseAtomicDB API over a socket.
    """
    logger = logging.getLogger('trinity._utils.socket.IPCSocketServer')

    def __init__(self) -> None:
        """
        The AtomicDatabaseAPI that this wraps must be threadsafe.
        """
        self._started = threading.Event()
        self._stopped = threading.Event()

    @property
    def is_started(self) -> bool:
        return self._started.is_set()

    @property
    def is_running(self) -> bool:
        return self.is_started and not self.is_stopped

    @property
    def is_stopped(self) -> bool:
        return self._stopped.is_set()

    def wait_started(self) -> None:
        self._started.wait()

    def wait_stopped(self) -> None:
        self._stopped.wait()

    def start(self, ipc_path: pathlib.Path) -> None:
        threading.Thread(
            name=f"{self}:{ipc_path}",
            target=self.serve,
            args=(ipc_path,),
            daemon=True,
        ).start()
        self.wait_started()

    def stop(self) -> None:
        self._stopped.set()

    def _close_socket_on_stop(self, sock: socket.socket) -> None:
        # This function runs in the background waiting for the `stop` Event to
        # be set at which point it closes the socket, causing the server to
        # shutdown.  This allows the server threads to be cleanly closed on
        # demand.
        self.wait_stopped()

        try:
            sock.shutdown(socket.SHUT_RD)
        except OSError as e:
            # on mac OS this can result in the following error:
            # OSError: [Errno 57] Socket is not connected
            if e.errno != errno.ENOTCONN:
                raise

        sock.close()

    @contextlib.contextmanager
    def run(self, ipc_path: pathlib.Path) -> Iterator[None]:
        self.start(ipc_path)
        try:
            yield
        finally:
            self.stop()

            if ipc_path.exists():
                ipc_path.unlink()

    def serve(self, ipc_path: pathlib.Path) -> None:
        self.logger.debug("Starting %s server over IPC socket: %s", self, ipc_path)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            # background task to close the socket.
            threading.Thread(
                name="_close_socket_on_stop",
                target=self._close_socket_on_stop,
                args=(sock,),
                daemon=True,
            ).start()

            # These options help fix an issue with the socket reporting itself
            # already being used since it accepts many client connection.
            # https://stackoverflow.com/questions/6380057/python-binding-socket-address-already-in-use
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(str(ipc_path))
            sock.listen(1)

            self._started.set()

            while self.is_running:
                try:
                    conn, addr = sock.accept()
                except (ConnectionAbortedError, OSError) as err:
                    self.logger.debug("Server stopping: %s", err)
                    self._stopped.set()
                    break
                self.logger.debug('Server accepted connection: %r', addr)
                threading.Thread(
                    name="_serve_conn",
                    target=self._serve_conn,
                    args=(conn,),
                    daemon=True,
                ).start()

    @abstractmethod
    def serve_conn(self, sock: BufferedSocket) -> None:
        ...

    def _serve_conn(self, raw_socket: socket.socket) -> None:
        self.logger.debug("%s: starting client handler for %s", self, raw_socket)

        with raw_socket:
            sock = BufferedSocket(raw_socket)

            self.serve_conn(sock)
