import time
import asyncio

class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets = {}
        self.lock = asyncio.Lock()

    async def acquire(self, api_key: str, tokens: int = 1) -> bool:
        async with self.lock:
            now = time.time()
            if api_key not in self.buckets:
                self.buckets[api_key] = {"tokens": self.capacity, "last_refill": now}
            
            bucket = self.buckets[api_key]
            elapsed = now - bucket["last_refill"]
            
            # Refill tokens based on elapsed time
            refill_amount = elapsed * self.refill_rate
            if refill_amount > 0:
                bucket["tokens"] = min(self.capacity, bucket["tokens"] + refill_amount)
                bucket["last_refill"] = now
                
            if bucket["tokens"] >= tokens:
                bucket["tokens"] -= tokens
                return True
            return False

    def get_tokens(self, api_key: str) -> float:
        # For display purposes
        if api_key in self.buckets:
            return self.buckets[api_key]["tokens"]
        return self.capacity
