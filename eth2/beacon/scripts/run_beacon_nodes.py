#!/usr/bin/env python

import asyncio
from collections import (
    defaultdict,
)
import logging
import signal
import sys
import time
from typing import (
    Dict,
    List,
    MutableSet,
    NamedTuple,
)

from pathlib import Path


dir_root = Path("/tmp/aaaa")
dir_alice = dir_root / "alice"
dir_bob = dir_root / "bob"
port_alice = 30304
port_bob = 30305
num_validators = 5
cmd_gen_testnet_files = f"trinity-beacon testnet --num={num_validators} --network-dir={dir_root}"
cmd_alice = f"trinity-beacon --port={port_alice} --trinity-root-dir={dir_alice} --beacon-nodekey=6b94ffa2d9b8ee85afb9d7153c463ea22789d3bbc5d961cc4f63a41676883c19 -l debug"  # noqa: E501
cmd_bob = f"trinity-beacon --port={port_bob} --trinity-root-dir={dir_bob} --beacon-nodekey=f5ad1c57b5a489fc8f21ad0e5a19c1f1a60b8ab357a2100ff7e75f3fa8a4fd2e --bootstrap_nodes=enode://c289557985d885a3f13830a475d649df434099066fbdc840aafac23144f6ecb70d7cc16c186467f273ad7b29707aa15e6a50ec3fde35ae2e69b07b3ddc7a36c7@127.0.0.1:{port_alice} -l debug"  # noqa: E501
file_genesis_json = "genesis.json"
file_validators_json = "validators.json"

time_bob_wait_for_alice = 15


async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return proc


class NodeEvent(NamedTuple):
    name: str
    pattern: str
    # TODO: dependent event?
    timeout: int


class EventTimeOutError(Exception):
    pass


SERVER_RUNNING = NodeEvent(name="server running", pattern="Running server", timeout=60)
START_SYNCING = NodeEvent(name="start syncing", pattern="their head slot", timeout=200)


nodes_to_stop = []


def stop_all_nodes():
    global nodes_to_stop
    for node in nodes_to_stop:
        print(f"Stopping node={node}")
        node.stop()


class Node:
    name: str
    cmd: str
    start_time: float
    proc: asyncio.subprocess.Process
    # TODO: use CancelToken instead
    tasks: List[asyncio.Task]
    events_expected: Dict[str, MutableSet[NodeEvent]]
    has_event_happend: Dict[NodeEvent, bool]

    logger = logging.getLogger("eth2.beacon.scripts.run_beacon_nodes.Node")

    def __init__(self, name: str, cmd: str) -> None:
        self.name = name
        self.cmd = cmd
        self.tasks = []
        self.start_time = time.monotonic()
        self.events_expected = {}
        self.events_expected["stdout"] = set()
        self.events_expected["stderr"] = set([SERVER_RUNNING])
        self.has_event_happend = defaultdict(lambda: False)
        asyncio.ensure_future(self._run(self.cmd))

    def __repr__(self) -> str:
        return f"<Node {self.name} {self.proc}"

    def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        self.proc.terminate()

    def add_event(self, from_stream: str, event: NodeEvent) -> None:
        if from_stream not in ("stdout", "stderr"):
            return
        self.events_expected[from_stream].add(event)

    async def _run(self, cmd: str) -> None:
        print(f"Spinning up {self.name}")
        self.proc = await run(cmd)
        self.tasks.append(asyncio.ensure_future(self._print_logs('stdout', self.proc.stdout)))
        self.tasks.append(asyncio.ensure_future(self._print_logs('stderr', self.proc.stderr)))
        try:
            await self._event_monitor()
        except EventTimeOutError as e:
            print(e)
            self.logger.debug(e)
            # FIXME: nasty
            stop_all_nodes()
            sys.exit(2)

    async def _event_monitor(self):
        while True:
            for from_stream, events in self.events_expected.items():
                for event in events:
                    current_time = time.monotonic()
                    ellapsed_time = current_time - self.start_time
                    if not self.has_event_happend[event] and (ellapsed_time > event.timeout):
                        raise EventTimeOutError(
                            f"Event {event.name!r} is time out, "
                            f"which should have occurred in {from_stream}."
                        )
            await asyncio.sleep(0.1)

    async def _print_logs(self, from_stream: str, stream_reader: asyncio.StreamReader) -> None:
        async for line_bytes in stream_reader:
            line = line_bytes.decode('utf-8').replace('\n', '')
            # TODO: Preprocessing
            self._record_happenning_event(from_stream, line)
            print(f"{self.name}.{from_stream}: {line}")

    def _record_happenning_event(self, from_stream, line):
        for event in self.events_expected[from_stream]:
            if event.pattern in line:
                self.logger.debug(f"event \"event.name\" occurred in {from_stream}")
                self.has_event_happend[event] = True


async def main():
    proc = await run(
        f"rm -rf {dir_root}"
    )
    await proc.wait()
    # proc = await run(
    #     f"mkdir -p {dir_alice} {dir_bob}"
    # )
    proc = await run(
        f"mkdir -p {dir_root}"
    )
    await proc.wait()

    proc = await run(cmd_gen_testnet_files)
    await proc.wait()

    def sigint_handler(sig, frame):
        stop_all_nodes()
        sys.exit(123)

    signal.signal(signal.SIGINT, sigint_handler)

    node_alice = Node('Alice\tc2895', cmd_alice)
    nodes_to_stop.append(node_alice)

    print(f"Sleeping {time_bob_wait_for_alice} seconds to wait until Alice is initialized")
    await asyncio.sleep(time_bob_wait_for_alice)

    node_bob = Node('Bob\t0e01b', cmd_bob)
    # node_bob.add_event("stderr", START_SYNCING)
    nodes_to_stop.append(node_bob)

    await asyncio.sleep(1000000)


asyncio.get_event_loop().run_until_complete(main())
