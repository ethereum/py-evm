import collections
from typing import Deque

from bloom_filter import (
    BloomFilter
)


class RollingBloom:
    def __init__(self, generation_size: int, max_generations: int) -> None:
        if generation_size < 1:
            raise ValueError(f"generation_size must be a positive integer: got {generation_size}")
        if max_generations < 2:
            raise ValueError(f"max_generations must be 2 or more: got {max_generations}")
        self._max_bloom_elements = generation_size
        self._max_history = max_generations - 1
        self._history: Deque[BloomFilter] = collections.deque()
        self._active = BloomFilter(max_elements=self._max_bloom_elements)
        self._items_in_active = 0

    def add(self, key: bytes) -> None:
        # before adding the value check if the active bloom filter is full.  If
        # so, push it into the history and make a new one.
        if self._items_in_active >= self._max_bloom_elements:
            self._history.appendleft(self._active)
            self._active = BloomFilter(max_elements=self._max_bloom_elements)
            self._items_in_active = 0

            # discard any old history that is older than the number of
            # generations we should be retaining.
            while len(self._history) > self._max_history:
                self._history.pop()

        self._active.add(key)
        self._items_in_active += 1

    def __contains__(self, key: bytes) -> bool:
        if key in self._active:
            return True
        return any(key in bloom for bloom in self._history)
