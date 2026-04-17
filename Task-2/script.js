const chatBox = document.getElementById("chat-box");
const input = document.getElementById("message-input");
const client_name = prompt("Enter your name:");

const ws = new WebSocket(`ws://localhost:8000/ws`);

let currentRoom = "general";

function getTime() {
  const now = new Date();
  return now.getHours() + ":" + String(now.getMinutes()).padStart(2, "0");
}

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
function updateUsers(users) {
  const ul = document.getElementById("users");
  ul.innerHTML = "";

  const liGeneral = document.createElement("li");
  liGeneral.textContent = "# General";
  liGeneral.onclick = () => switchRoom("general");
  ul.appendChild(liGeneral);

  users.forEach((user) => {
    if (user === client_name) return;
    const li = document.createElement("li");
    li.textContent = user;
    li.onclick = () => switchRoom(user);
    ul.appendChild(li);
  });
}

let typingDiv;

ws.onmessage = function (event) {
  const data = JSON.parse(event.data);

  if (data.type === "history") {
    data.messages.forEach((msg) => {
      const cssClass = msg.sender === client_name ? "sent" : "received";
      const prefix = msg.sender === client_name ? "You" : msg.sender;
      createMessage(`${prefix}: ${msg.content}`, cssClass);
    });
  }

  if (data.type === "message") {
    createMessage(`${data.sender}: ${data.content}`, "received");
  }

  if (data.type === "system") {
    createMessage(data.content, "received");
  }

  if (data.type === "presence") {
    createMessage(data.content, "received");
  }

  if (data.type === "typing") {
    showTyping(data.sender);
  }
  if (data.type === "users") {
    updateUsers(data.users);
  }
};

function switchRoom(targetUser) {
  const newRoom =
    targetUser === "general"
      ? "general"
      : [client_name, targetUser].sort().join("_");
  if (currentRoom === newRoom) return;

  currentRoom = newRoom;
  document.getElementById("chat-title").textContent =
    targetUser === "general" ? "General Chat" : targetUser;
  chatBox.innerHTML = "";

  ws.send(JSON.stringify({ type: "join", room: currentRoom }));
}

ws.onopen = function () {
  ws.send(JSON.stringify({ client_name: client_name }));

  ws.send(
    JSON.stringify({
      type: "join",
      room: currentRoom,
    }),
  );
};

function sendMessage() {
  const text = input.value.trim();
  if (text === "") return;

  createMessage(`You: ${text}`, "sent");
  ws.send(
    JSON.stringify({
      type: "message",
      room: currentRoom,
      content: text,
    }),
  ); // send to server

  input.value = "";
}

let typingTimer;
input.addEventListener("input", () => {
  ws.send(
    JSON.stringify({
      type: "typing",
      room: currentRoom,
    }),
  );

  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => {
    typingTimer = null;
  }, 1000);
});

input.addEventListener("keypress", function (e) {
  if (e.key === "Enter") {
    e.preventDefault();
    sendMessage();
  }
});

ws.onclose = function () {
  createMessage("Disconnected from server", "received");
};

ws.onerror = function () {
  createMessage("Connection error", "received");
};

function showTyping(sender) {
  if (typingDiv) typingDiv.remove();

  typingDiv = document.createElement("div");
  typingDiv.classList.add("typing");
  typingDiv.textContent = `${sender} is typing...`;

  chatBox.appendChild(typingDiv);

  setTimeout(() => {
    if (typingDiv) typingDiv.remove();
  }, 1500);
}
