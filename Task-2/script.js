const chatBox = document.getElementById("chat-box");
const input = document.getElementById("message-input");

// 🔌 WebSocket connection
const clientId = Math.floor(Math.random() * 1000);
const ws = new WebSocket(`ws://localhost:8000/ws/${clientId}`);

// 🕒 Time function
function getTime() {
  const now = new Date();
  return now.getHours() + ":" + String(now.getMinutes()).padStart(2, "0");
}

// 💬 Create message UI
function createMessage(text, type) {
  const msgDiv = document.createElement("div");
  msgDiv.classList.add("message", type);

  const msgText = document.createElement("div");
  msgText.textContent = text;

  const time = document.createElement("div");
  time.classList.add("timestamp");
  time.textContent = getTime();

  msgDiv.appendChild(msgText);
  msgDiv.appendChild(time);

  chatBox.appendChild(msgDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// 📩 Receive message from server
ws.onmessage = function (event) {
  const data = JSON.parse(event.data);

  if (data.type === "message") {
    createMessage(`${data.sender}: ${data.content}`, "received");
  }

  if (data.type === "system") {
    createMessage(data.content, "received");
  }
};

ws.onopen = function () {
  ws.send(
    JSON.stringify({
      type: "join",
      room: "general",
    }),
  );
};

// 🚀 Send message
function sendMessage() {
  const text = input.value.trim();
  if (text === "") return;

  createMessage(text, "sent"); // show own message
  ws.send(
    JSON.stringify({
      type: "message",
      room: "general",
      content: text,
    }),
  ); // send to server

  input.value = "";
}

// ⌨️ Enter key support
input.addEventListener("keypress", function (e) {
  if (e.key === "Enter") {
    sendMessage();
  }
});

// ❌ Handle disconnect
ws.onclose = function () {
  createMessage("Disconnected from server", "received");
};

ws.onerror = function () {
  createMessage("Connection error", "received");
};
