const form = document.getElementById('chat-form');
const input = document.getElementById('chat-input');
const messages = document.getElementById('messages');
const template = document.getElementById('message-template');

function agentClass(name) {
    return 'agent-' + name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

function addMessage(text, cls, role) {
    const node = template.content.cloneNode(true);
    const div = node.querySelector('.message');
    div.classList.add(cls);
    node.querySelector('.role-badge').textContent = role || cls;
    node.querySelector('.text').textContent = text;
    node.querySelector('.timestamp').textContent = new Date().toLocaleTimeString();
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
}

function queueMessages(list) {
    let delay = 0;
    list.forEach(m => {
        delay += 10000 + Math.random() * 10000;
        setTimeout(() => addMessage(m.text, agentClass(m.name), m.name), delay);
    });
}

async function startForum() {
    const res = await fetch('/forum/start');
    const data = await res.json();
    queueMessages(data.messages);
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMessage(text, 'user', 'You');
    input.value = '';
    const res = await fetch('/forum/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    queueMessages(data.messages);
});

window.addEventListener('DOMContentLoaded', startForum);
