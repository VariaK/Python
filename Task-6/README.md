# API Gateway with Rate Limiting & Caching

An asynchronous reverse-proxy API gateway built using `FastAPI` and `aiohttp`. It routes requests to downstream microservices and implements crucial gateway patterns.

## Features

1. **Reverse Proxy & Routing**: Routes `/api/users/**`, `/api/orders/**`, and `/api/products/**` to corresponding mock downstream services using high-performance `aiohttp` client sessions.
2. **Token-Bucket Rate Limiting**: Implements a per-API-key token-bucket algorithm to restrict traffic (e.g., 50 requests/min).
3. **Response Caching**: Caches successful `GET` responses using `Redis` (`redis.asyncio`) with a configurable TTL, falling back to an in-memory mock cache if Redis is unavailable.
4. **Circuit Breaker Pattern**: Monitors downstream service health. If a service fails 5 consecutive times, the circuit opens, returning fast `503 Service Unavailable` responses with a fallback payload. It automatically transitions to half-open after a timeout.
5. **Health Dashboard**: Exposes a `/health` endpoint that dynamically shows the state of the system, including service status, latencies, circuit states, and cache hits.

## Setup & Running

**1. Create a virtual environment and install dependencies:**
```powershell
# If using the root venv:
..\venv\Scripts\pip install -r requirements.txt
```

**2. Run the Demo:**
The included `demo.py` script automatically spins up the downstream mock services, starts the FastAPI gateway, and sends a sequence of requests to demonstrate cache hits, rate limiting, and the circuit breaker in action.

```powershell
..\venv\Scripts\python demo.py
```

### Expected Output
When running `demo.py`, you will see a detailed request log directly in the console matching the assignment specifications:
- `CACHE HIT` logs with TTL and latency.
- `PROXY` logs with downstream service routing.
- `RATE LIMITED` logs showing 429 Too Many Requests.
- `CIRCUIT OPEN` logs displaying the fallback payload.
- A neatly formatted ASCII `=== Health Dashboard ===`.

## Components
- `gateway.py`: The FastAPI application, handling startup events, routing, and assembling middleware.
- `rate_limiter.py`: The token-bucket rate limiter.
- `circuit_breaker.py`: State-machine implementation of the circuit breaker.
- `cache.py`: Redis wrapper with in-memory fallback.
- `mock_services.py`: `aiohttp`-based servers simulating downstream microservices.
- `demo.py`: Multiprocessing script that orchestrates the entire setup for quick testing.
