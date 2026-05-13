import asyncio
from aiohttp import web

async def handle_user(request):
    path = request.path
    return web.json_response({"service": "user", "path": path, "status": "ok"})

async def handle_order(request):
    path = request.path
    if "7891" in path or "fail" in path:
        # Simulate a timeout/error
        await asyncio.sleep(2)
        return web.json_response({"error": "Internal Server Error"}, status=500)
    
    return web.json_response({"service": "order", "path": path, "status": "ok"})

async def handle_product(request):
    path = request.path
    return web.json_response({"service": "product", "path": path, "status": "ok"})

async def make_app(handler):
    app = web.Application()
    app.router.add_route('*', '/{path:.*}', handler)
    return app

async def run_servers():
    app_user = await make_app(handle_user)
    app_order = await make_app(handle_order)
    app_product = await make_app(handle_product)

    runner_user = web.AppRunner(app_user)
    runner_order = web.AppRunner(app_order)
    runner_product = web.AppRunner(app_product)

    await runner_user.setup()
    await runner_order.setup()
    await runner_product.setup()

    site_user = web.TCPSite(runner_user, 'localhost', 3001)
    site_order = web.TCPSite(runner_order, 'localhost', 3002)
    site_product = web.TCPSite(runner_product, 'localhost', 3003)

    await site_user.start()
    await site_order.start()
    await site_product.start()
    
    # Keep alive
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(run_servers())
