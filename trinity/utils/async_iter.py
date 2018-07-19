from typing import (
    AsyncIterable,
    Set,
)


async def contains_all(async_gen: AsyncIterable[str], keywords: Set[str]) -> bool:
    """
    Check wether an ``AsyncIterable[str]`` contains all of the given keywords. The keywords
    can be embedded in some larger string. Return ``True`` as soon as all keywords were matched.
    If not all keywords were matched by the time that the async iterable is done, return ``False``.
    """
    seen_keywords: Set[str] = set()
    async for line in async_gen:
        for check in keywords - seen_keywords:
            if check in line:
                seen_keywords.add(check)
        if seen_keywords == keywords:
            return True

    return False
