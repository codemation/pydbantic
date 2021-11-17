import time
import logging
from collections import deque
from pickle import dumps, loads
import asyncio

import aioredis


class Redis:
    def __init__(self,
        url: str = "redis://localhost",
        log: logging.Logger = logging.getLogger(__name__)
    ):
        self.redis = aioredis.from_url(url)
        self.log = log

    async def get(self, key):
        cache = await self.redis.get(key)
        if cache:
            return loads(cache)[0]
        return None
        
    async def set(self, cached_key, row_and_flag: tuple):
        row, flag = row_and_flag
        await asyncio.gather(
            self.redis.set(
                cached_key, dumps(([dict(r) for r in row], flag))
            ),
            self.redis.rpush(f'f_{flag}', cached_key)
        )

    async def invalidate(self, flag: str):
        """
        invalidates cache flagged input flag str
        """
        cache_keys = await self.redis.lrange(f'f_{flag}', 0, -1)
        
        if not cache_keys:
            return
        
        await self.redis.delete(f'f_{flag}', *cache_keys)
        self.log.warning(f"cache flag {flag} invalidated {len(cache_keys)} items")



class Cache:
    """
    Used for managing cache rotation & retention, max len
    """
    def __init__(self,
        size: int = 1000,
        log: logging.Logger = logging.getLogger(__name__)
    ):
        self.size = size
        self.timestamp_to_cache = {}
        self.access_history = deque()

        self.cache = {}
        self.flags = {}

        self.log = log
    def invalidate(self, flag: str):
        """
        invalidates cache flagged input flag str
        """
        if flag not in self.flags:
            return
        for timestamp in self.flags[flag]:
            if timestamp not in self.timestamp_to_cache:
                continue
            _,cached_key, _ = self.timestamp_to_cache[timestamp]
            del self.timestamp_to_cache[timestamp]
            del self.cache[cached_key]
        del self.flags[flag]
    def check_size_and_clear(self):
        if len(self.timestamp_to_cache) < self.size:
            return
        while len(self.timestamp_to_cache) >= self.size:
            cache_time = self.access_history.popleft()
            if cache_time not in self.timestamp_to_cache:
                continue
            _, cache_key, _ = self.timestamp_to_cache[cache_time]
            del self.timestamp_to_cache[cache_time]
            if cache_key in self.cache and self.cache[cache_key] != cache_time:
                continue
            del self.cache[cache_key]
            self.log.debug(f"# cach_key '{cache_key}' cleared due to cache length of {self.size} exceeded")

    def update_timestamp(self, cached_key, flag):
        if cached_key not in self:
            return

        old_time = self.cache[cached_key]
        new_time = time.time()

        self.timestamp_to_cache[new_time] = self.timestamp_to_cache[old_time]
        del self.timestamp_to_cache[old_time]

        self.cache[cached_key] = new_time
        self.flags[flag].add(new_time)
        self.access_history.append(new_time)
    def __iter__(self):
        return (
            (cache_key, self.timestamp_to_cache[timestamp][0]) 
            for cache_key, timestamp in self.cache.copy().items()
        )

    def __getitem__(self, cached_key):
        if cached_key not in self:
            return None

        cache_time = self.cache[cached_key]
        if cache_time not in self.timestamp_to_cache:
            del self.cache[cached_key]
            return None

        cache_row, _, flag = self.timestamp_to_cache[cache_time]
        self.update_timestamp(cached_key, flag)
        return cache_row

    def __setitem__(self, cached_key, row_and_flag: tuple):
        row, flag = row_and_flag
        cache_time = time.time()
        if cached_key in self.cache:
            old_cache_time = self.cache[cached_key]
            del self.timestamp_to_cache[old_cache_time]

        self.cache[cached_key] = cache_time
        self.timestamp_to_cache[cache_time] = (row, cached_key, flag)
        if flag:
            if flag not in self.flags:
                self.flags[flag] = set()
            self.flags[flag].add(cache_time)

        self.access_history.append(cache_time)
        self.check_size_and_clear()

    def __delitem__(self, cached_key) -> None:
        if cached_key not in self.cache:
            return

        cache_time = self.cache.pop(cached_key)
        if cache_time in self.timestamp_to_cache:
            del self.timestamp_to_cache[cache_time]

    def __contains__(self, cached_key):
        return cached_key in self.cache

async def cache_main():
    cache = Redis()
    await cache.set('test', ('value', 'test_flag'))
    cache_result = await cache.get('test')
    print('cache_result', cache_result)


if __name__ == '__main__':
    cache = Cache(size=50)
    for i in range(100):
        cache[i] = i, 'test'
    
    
    asyncio.run(cache_main())