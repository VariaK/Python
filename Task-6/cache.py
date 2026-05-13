import json
import time

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

class Cache:
    def __init__(self, redis_url="redis://localhost"):
        self.redis_url = redis_url
        self.client = None
        self.mock_cache = {}
        self.service_hits = {"users": 0, "orders": 0, "products": 0}

    async def connect(self):
        if redis is None:
            self.client = None
            return

        try:
            self.client = redis.from_url(self.redis_url)
            await self.client.ping()
        except Exception:
            self.client = None

    async def get(self, key: str, service: str = None):
        if self.client:
            try:
                val = await self.client.get(key)
                if val:
                    if service and service in self.service_hits:
                        self.service_hits[service] += 1
                    return json.loads(val)
            except Exception:
                pass
        else:
            if key in self.mock_cache:
                entry = self.mock_cache[key]
                if time.time() < entry['expiry']:
                    if service and service in self.service_hits:
                        self.service_hits[service] += 1
                    return entry['val']
                else:
                    del self.mock_cache[key]
        return None

    async def set(self, key: str, value: dict, ttl: int):
        if self.client:
            try:
                await self.client.set(key, json.dumps(value), ex=ttl)
            except Exception:
                pass
        else:
            self.mock_cache[key] = {'val': value, 'expiry': time.time() + ttl}

    async def get_ttl(self, key: str):
        if self.client:
            try:
                return await self.client.ttl(key)
            except Exception:
                return -1
        else:
            if key in self.mock_cache:
                return int(max(0, self.mock_cache[key]['expiry'] - time.time()))
            return -1
