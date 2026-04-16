from typing import List, Dict
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
import json
import sqlite3


conn = sqlite3.connect("chat.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room TEXT,
    sender TEXT,
    content TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

def save_message(room, sender, content):
    cursor.execute(
        "INSERT INTO messages (room, sender, content) VALUES (?, ?, ?)",
        (room, sender, content)
    )
    conn.commit()

def get_recent_messages(room, limit=20):
    cursor.execute(
        "SELECT sender, content FROM messages WHERE room=? ORDER BY id DESC LIMIT ?",
        (room, limit)
    )
    rows = cursor.fetchall()

    # reverse to show oldest first
    return [{"sender": r[0], "content": r[1]} for r in rows[::-1]]


app = FastAPI()
templates = Jinja2Templates(directory="templates")

class ConnectionManager:
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.rooms: Dict[str, List[str]] = {}

    
    async def connect(self,client_name: str, websocket: WebSocket):
        self.active_connections[client_name] = websocket

    def disconnect(self, client_name: str):
        # Remove from active connections
        if client_name in self.active_connections:
            del self.active_connections[client_name]

        # Remove from all rooms
        for room in self.rooms.values():
            if client_name in room:
                room.remove(client_name)

    async def send_to_user(self, client_name: str, message: dict):
        websocket = self.active_connections.get(client_name)
        if websocket:
            await websocket.send_text(json.dumps(message))

    async def broadcast_to_room(self, room: str, message: dict, sender_name: str):
        if room not in self.rooms:
            return

        for client_name in self.rooms[room]:
            if client_name == sender_name:
                continue  

            websocket = self.active_connections.get(client_name)
            if websocket:
                await websocket.send_text(json.dumps(message))

    async def broadcast_all_in_room(self, room: str, message: dict):
        if room not in self.rooms:
            return

        for username in self.rooms[room]:
            websocket = self.active_connections.get(username)
            if websocket:
                await websocket.send_text(json.dumps(message))

    def join_room(self, client_name: str, room: str):
        if room not in self.rooms:
            self.rooms[room] = []

        if client_name not in self.rooms[room]:
            self.rooms[room].append(client_name)


connectionmanager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request" : request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    
    await websocket.accept()
    data = await websocket.receive_text()
    data = json.loads(data)
    client_name = data.get("client_name")
    await connectionmanager.connect(client_name, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            data = json.loads(data)

            msg_type = data.get("type")

            if msg_type == "join":
                room = data.get("room")
                connectionmanager.join_room(client_name, room)

                history = get_recent_messages(room)
                await connectionmanager.send_to_user(client_name, {
                    "type": "history",
                    "messages": history
                })

                await connectionmanager.broadcast_to_room(room, {
                    "type": "system",
                    "content": f"{client_name} joined #{room}"
                }, client_name)
                await connectionmanager.broadcast_to_room(room, {
                    "type": "presence",
                    "content": f"{client_name} is online"
                }, client_name)
                await connectionmanager.broadcast_all_in_room(room, {
                    "type": "users",
                    "users": connectionmanager.rooms[room]
                })
            elif msg_type == "message":
                room = data.get("room")
                content = data.get("content")
                sender = f"{client_name}"
                save_message(room, sender, content) 

                await connectionmanager.broadcast_to_room(room, {
                    "type": "message",
                    "sender": f"{client_name}",
                    "content": content
                }, client_name)    
            
            elif msg_type == "typing":
                room = data.get("room")

                await connectionmanager.broadcast_to_room(room, {
                    "type": "typing",
                    "sender": f"{client_name}"
                }, client_name)
            
            
    except WebSocketDisconnect:
        connectionmanager.disconnect(client_name)
        for room in connectionmanager.rooms:
            await connectionmanager.broadcast_to_room(room, {
                "type": "presence",
                "content": f"{client_name} went offline"
            }, client_name)
        for room in connectionmanager.rooms:
            await connectionmanager.broadcast_to_room(room, {
                "type": "users",
                "users": connectionmanager.rooms[room]
            }, client_name)

