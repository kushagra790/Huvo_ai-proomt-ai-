let sessionId = localStorage.getItem("northstar_session_id");

const messages = document.querySelector("#messages");
const form = document.querySelector("#chatForm");
const input = document.querySelector("#messageInput");
const analytics = document.querySelector("#analytics");
const newChatButton = document.querySelector("#newChatButton");

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function setAnalytics(data) {
  analytics.textContent = JSON.stringify(data, null, 2);
}

async function sendMessage(text) {
  addMessage("user", text);
  input.value = "";
  input.disabled = true;

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      session_id: sessionId,
      message: text
    })
  });

  const data = await response.json();
  sessionId = data.session_id;
  localStorage.setItem("northstar_session_id", sessionId);
  addMessage("bot", data.reply);
  setAnalytics(data.analytics);
  input.disabled = data.ended;
  input.focus();
}

form.addEventListener("submit", event => {
  event.preventDefault();
  const text = input.value.trim();
  if (text) {
    sendMessage(text);
  }
});

newChatButton.addEventListener("click", () => {
  sessionId = null;
  localStorage.removeItem("northstar_session_id");
  messages.innerHTML = "";
  setAnalytics({});
  input.disabled = false;
  input.value = "";
  input.focus();
  addMessage("bot", "Hi, I am calling from Northstar Homes about Northstar One in Sector 79, Gurugram. How can I help you today?");
});

addMessage("bot", "Hi, I am calling from Northstar Homes about Northstar One in Sector 79, Gurugram. How can I help you today?");

