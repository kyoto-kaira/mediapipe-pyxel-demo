from __future__ import annotations

from queue import Queue
from typing import Protocol


class ThreadedProvider(Protocol):
    def start(self, out_queue: Queue) -> None: ...
    def stop(self) -> None: ...


class PollingProvider(Protocol):
    def poll(self, px, out_queue: Queue) -> None: ...


