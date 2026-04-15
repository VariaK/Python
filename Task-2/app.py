from typing import List, Dict
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
import json


app = FastAPI()
templates = Jinja2Templates(directory="templates")

class ConnectionManager:
    
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.rooms: Dict[str, List[int]] = {}

    
    async def connect(self,client_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: int):
        # Remove from active connections
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # Remove from all rooms
        for room in self.rooms.values():
            if client_id in room:
                room.remove(client_id)

    async def send_to_user(self, client_id: int, message: dict):
        websocket = self.active_connections.get(client_id)
        if websocket:
            await websocket.send_text(json.dumps(message))

    async def broadcast_to_room(self, room: str, message: dict, sender_id: int):
        if room not in self.rooms:
            return

        for client_id in self.rooms[room]:
            if client_id == sender_id:
                continue  

            websocket = self.active_connections.get(client_id)
            if websocket:
                await websocket.send_text(json.dumps(message))

    def join_room(self, client_id: int, room: str):
        if room not in self.rooms:
            self.rooms[room] = []

        if client_id not in self.rooms[room]:
            self.rooms[room].append(client_id)


connectionmanager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
def read_index(request: Request):
    
    return templates.TemplateResponse("index.html", {"request" : request})

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    
    await connectionmanager.connect(client_id, websocket)
    try:
        while True:
            
            data = await websocket.receive_text()
            data = json.loads(data)
            msg_type = data.get("type")

            if msg_type == "join":
                room = data.get("room")
                connectionmanager.join_room(client_id, room)

                await connectionmanager.broadcast_to_room(room, {
                    "type": "system",
                    "content": f"Client #{client_id} joined #{room}"
                }, client_id)
            elif msg_type == "message":
                room = data.get("room")
                content = data.get("content")

                await connectionmanager.broadcast_to_room(room, {
                    "type": "message",
                    "sender": f"Client #{client_id}",
                    "content": content
                }, client_id)    
            
            
    except WebSocketDisconnect:
        connectionmanager.disconnect(client_id)
        for room in connectionmanager.rooms:
            await connectionmanager.broadcast_to_room(room, {
                "type": "system",
                "content": f"Client #{client_id} left the chat"
            }, client_id)