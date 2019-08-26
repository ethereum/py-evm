#!/usr/bin/env python

import asyncio
from collections import defaultdict
import logging
from pathlib import Path
import signal
import sys
import time
from typing import ClassVar, Dict, List, MutableSet, NamedTuple, Optional, Tuple

from eth_keys.datatypes import PrivateKey
from eth_utils import remove_0x_prefix
from libp2p.peer.id import ID
from multiaddr import Multiaddr

from trinity.protocol.bcc_libp2p.utils import peer_id_from_pubkey


async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    return proc


class Log(NamedTuple):
    name: str
    pattern: str
    # TODO: probably we can add dependent relationship between logs?
    timeout: int


class EventTimeOutError(Exception):
    pass


SERVER_RUNNING = Log(name="server running", pattern="Running server", timeout=60)
START_SYNCING = Log(name="start syncing", pattern="their head slot", timeout=200)


class Node:
    name: str
    node_privkey: str
    port: int
    preferred_nodes: Tuple["Node", ...]

    start_time: float
    proc: asyncio.subprocess.Process
    # TODO: use CancelToken instead
    tasks: List[asyncio.Task]
    logs_expected: Dict[str, MutableSet[Log]]
    has_log_happened: Dict[Log, bool]

    dir_root: ClassVar[Path] = Path("/tmp/aaaa")
    running_nodes: ClassVar[List] = []
    logger: ClassVar[logging.Logger] = logging.getLogger(
        "eth2.beacon.scripts.run_beacon_nodes.Node"
    )

    def __init__(
        self,
        name: str,
        node_privkey: str,
        port: int,
        preferred_nodes: Optional[Tuple["Node", ...]] = None,
    ) -> None:
        self.name = name
        self.node_privkey = PrivateKey(bytes.fromhex(node_privkey))
        self.port = port
        if preferred_nodes is None:
            preferred_nodes = []
        self.preferred_nodes = preferred_nodes

        self.tasks = []
        self.start_time = time.monotonic()
        self.logs_expected = {}
        self.logs_expected["stdout"] = set()
        self.logs_expected["stderr"] = set()
        self.add_log("stderr", SERVER_RUNNING)
        self.has_log_happened = defaultdict(lambda: False)

    def __repr__(self) -> str:
        return f"<Node {self.logging_name} {self.proc}>"

    @property
    def logging_name(self) -> str:
        return f"{self.name}@{str(self.peer_id)[2:8]}"

    @property
    def root_dir(self) -> Path:
        return self.dir_root / self.name

    @property
    def peer_id(self) -> ID:
        return peer_id_from_pubkey(self.node_privkey.public_key)

    @property
    def maddr(self) -> Multiaddr:
        return Multiaddr(f"/ip4/127.0.0.1/tcp/{self.port}/p2p/{self.peer_id}")

    @property
    def cmd(self) -> str:
        _cmds = [
            "trinity-beacon",
            f"--port={self.port}",
            f"--trinity-root-dir={self.root_dir}",
            f"--beacon-nodekey={remove_0x_prefix(self.node_privkey.to_hex())}",
            "--disable-discovery",
            "--network-tracking-backend=do-not-track",
            "--disable-upnp",
            "-l debug2",
        ]
        if len(self.preferred_nodes) != 0:
            preferred_nodes_str = ",".join(
                [str(node.maddr) for node in self.preferred_nodes]
            )
            _cmds.append(f"--preferred_nodes={preferred_nodes_str}")
        _cmd = " ".join(_cmds)
        return _cmd

    def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        self.proc.terminate()

    @classmethod
    def stop_all_nodes(cls) -> None:
        for node in cls.running_nodes:
            print(f"Stopping node={node}")
            node.stop()

    def add_log(self, from_stream: str, log: Log) -> None:
        if from_stream not in ("stdout", "stderr"):
            return
        self.logs_expected[from_stream].add(log)

    async def run(self) -> None:
        print(f"Spinning up {self.name}")
        self.proc = await run(self.cmd)
        self.running_nodes.append(self)
        self.tasks.append(
            asyncio.ensure_future(self._print_logs("stdout", self.proc.stdout))
        )
        self.tasks.append(
            asyncio.ensure_future(self._print_logs("stderr", self.proc.stderr))
        )
        try:
            await self._log_monitor()
        except EventTimeOutError as e:
            self.logger.debug(e)
            # FIXME: nasty
            self.stop_all_nodes()
            sys.exit(2)

    async def _log_monitor(self) -> None:
        while True:
            for from_stream, logs in self.logs_expected.items():
                for log in logs:
                    current_time = time.monotonic()
                    ellapsed_time = current_time - self.start_time
                    if not self.has_log_happened[log] and (ellapsed_time > log.timeout):
                        raise EventTimeOutError(
                            f"{self.logging_name}: log {log.name!r} is time out, "
                            f"which should have occurred in {from_stream}."
                        )
            await asyncio.sleep(0.1)

    async def _print_logs(
        self, from_stream: str, stream_reader: asyncio.StreamReader
    ) -> None:
        async for line_bytes in stream_reader:
            line = line_bytes.decode("utf-8").replace("\n", "")
            # TODO: Preprocessing
            self._record_happenning_logs(from_stream, line)
            print(f"{self.logging_name}.{from_stream}\t: {line}")

    def _record_happenning_logs(self, from_stream: str, line: str) -> None:
        for log in self.logs_expected[from_stream]:
            if log.pattern in line:
                self.logger.debug('log "log.name" occurred in %s', from_stream)
                self.has_log_happened[log] = True


async def main():
    num_validators = 9
    genesis_delay = 20

    proc = await run(f"rm -rf {Node.dir_root}")
    await proc.wait()
    proc = await run(f"mkdir -p {Node.dir_root}")
    await proc.wait()

    print("Generating genesis file")
    proc = await run(
        " ".join(
            (
                "trinity-beacon",
                "testnet",
                f"--num={num_validators}",
                f"--network-dir={Node.dir_root}",
                f"--genesis-delay={genesis_delay}",
            )
        )
    )
    await proc.wait()

    def sigint_handler(sig, frame):
        Node.stop_all_nodes()
        sys.exit(123)

    signal.signal(signal.SIGINT, sigint_handler)

    node_alice = Node(
        name="alice",
        node_privkey="6b94ffa2d9b8ee85afb9d7153c463ea22789d3bbc5d961cc4f63a41676883c19",
        port=30304,
        preferred_nodes=[],
    )
    node_bob = Node(
        name="bob",
        node_privkey="f5ad1c57b5a489fc8f21ad0e5a19c1f1a60b8ab357a2100ff7e75f3fa8a4fd2e",
        port=30305,
        preferred_nodes=[node_alice],
    )
    node_alice.preferred_nodes = [node_bob]

    asyncio.ensure_future(node_alice.run())
    asyncio.ensure_future(node_bob.run())

    await asyncio.sleep(1000000)


asyncio.get_event_loop().run_until_complete(main())
