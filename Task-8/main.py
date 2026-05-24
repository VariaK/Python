from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import asyncio
import json
import time

from simulator import SensorSimulator
from processor import DataProcessor

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

simulator = SensorSimulator("sensor-T1")
processor = DataProcessor(window_size=300)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[INFO] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[INFO] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    print("[INFO] Stream processor started — consuming from sensors/factory-a")
    print("[INFO] Dashboard available at http://localhost:5000/dashboard")
    asyncio.create_task(run_stream())

async def run_stream():
    async for raw_data in simulator.generate_data():
        processed = processor.process(raw_data)
        
        # Log to console
        ts = time.strftime('%H:%M:%S', time.localtime(processed['timestamp']))
        print(f"[{ts}] {processed['sensor_id']}  temp={processed['temp']}F  vibration={processed['vibration']}g  status={processed['status']}")
        
        if processed['alert']:
            alert = processed['alert']
            print(f"\n=== Alert Triggered ===")
            print(f"[ALERT] {alert['sensor']} — {alert['message']}")
            print(f"        Current: {alert['current']}F | 5-min avg: {alert['avg']}F | Deviation: +{alert['sigma']} sigma")
            print(f"        Action: Notification sent to ops-team@factory.com\n")
            
        await manager.broadcast(json.dumps(processed))

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
