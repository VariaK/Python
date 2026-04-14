const chatBox = document.getElementById("chat-box");
const input = document.getElementById("message-input");

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

function sendMessage() {
  const text = input.value.trim();
  if (text === "") return;

  createMessage(text, "sent");
  input.value = "";

  simulateReply();
}

function simulateReply() {
  const replies = [
    "Really? Tell me more",
    "That's cool, Keep Going",
    "Tell me more...",
    "Go on...",
    "Keep going...",
  ];

  const randomReply = replies[Math.floor(Math.random() * replies.length)];

  setTimeout(
    () => {
      createMessage(randomReply, "received");
    },
    1000 + Math.random() * 2000,
  );
}

input.addEventListener("keypress", function (e) {
  if (e.key === "Enter") {
    sendMessage();
  }
});
