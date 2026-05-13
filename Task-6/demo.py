import asyncio
import httpx
import uvicorn
import multiprocessing
import time
import sys
from mock_services import run_servers

def start_services():
    asyncio.run(run_servers())

def start_gateway():
    sys.stdout.reconfigure(line_buffering=True)
    uvicorn.run("gateway:app", host="0.0.0.0", port=8080, log_level="critical")

async def run_demo():
    print("Waiting for services to start...")
    await asyncio.sleep(4)
    
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8080") as client:
            await client.get("/api/products/42", headers={"x-api-key": "api_key_9x3f"})
            await asyncio.sleep(0.1)
            await client.get("/api/products/42", headers={"x-api-key": "api_key_9x3f"})
            await asyncio.sleep(0.1)
            await client.get("/api/orders/latest", headers={"x-api-key": "api_key_9x3f"})
            await asyncio.sleep(0.1)
            
            headers = {"x-api-key": "api_key_b2k7"}
            reqs = [client.post("/api/users/signup", headers=headers) for _ in range(50)]
            await asyncio.gather(*reqs)
            await client.post("/api/users/signup", headers=headers)
            await asyncio.sleep(0.1)
            
            for _ in range(5):
                await client.get("/api/orders/fail", headers={"x-api-key": "api_key_m4n1"})
            await asyncio.sleep(0.1)
            
            await client.get("/api/orders/7891", headers={"x-api-key": "api_key_m4n1"})
            await asyncio.sleep(0.1)
            
            await client.get("/health")
            await asyncio.sleep(1) # Give time for prints to flush
    except Exception as e:
        print(f"Error during demo: {e}")

if __name__ == "__main__":
    p_services = multiprocessing.Process(target=start_services)
    p_gateway = multiprocessing.Process(target=start_gateway)
    
    p_services.start()
    p_gateway.start()
    
    try:
        asyncio.run(run_demo())
    finally:
        p_services.terminate()
        p_gateway.terminate()
        p_services.join()
        p_gateway.join()
